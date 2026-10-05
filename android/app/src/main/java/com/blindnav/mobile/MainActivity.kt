package com.blindnav.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.camera.view.PreviewView
import com.blindnav.mobile.inference.InferencePipeline
import com.blindnav.mobile.inference.OnnxYoloDetector
import com.blindnav.mobile.inference.RuntimeMetrics
import com.blindnav.mobile.feedback.FeedbackAction
import com.blindnav.mobile.feedback.FeedbackDispatcher
import com.blindnav.mobile.feedback.FeedbackPriority
import com.blindnav.mobile.guidance.GeometryWalkableRegionEstimator
import com.blindnav.mobile.guidance.GuidanceEngine
import com.blindnav.mobile.guidance.GuidanceState
import com.blindnav.mobile.overlay.TrajectoryOverlayView
import com.blindnav.mobile.risk.TemporalRiskEngine
import com.blindnav.mobile.sensing.PhoneCameraFrameSource

/** Minimal shell; camera binding is intentionally kept behind FrameSource. */
class MainActivity : ComponentActivity() {
    private var cameraSource: PhoneCameraFrameSource? = null
    private var detector: AutoCloseable? = null
    private var feedbackDispatcher: FeedbackDispatcher? = null
    // The phone path deliberately uses one broad two-wheeler model.  Static
    // targets are filtered by the temporal risk engine; a second person model
    // made the first phone build too slow for live use.
    private val riskEngine = TwoWheelerRuntimeConfig.createRiskEngine()
    private val walkableRegionEstimator = GeometryWalkableRegionEstimator()
    private val guidanceEngine = GuidanceEngine()
    private val runtimeMetrics = RuntimeMetrics()
    private var statusText: TextView? = null
    private var previewView: PreviewView? = null
    private var trajectoryOverlay: TrajectoryOverlayView? = null

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) startInference() else showStatus("需要相机权限才能运行感知")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.status_text)
        previewView = findViewById(R.id.preview_view)
        trajectoryOverlay = findViewById(R.id.trajectory_overlay)
        feedbackDispatcher = FeedbackDispatcher(this)
        findViewById<Button>(R.id.feedback_test_button).setOnClickListener {
            runFeedbackSelfTest()
        }
        intent.getStringExtra(EXTRA_RISK_REPORT_JSON)?.let { reportJson ->
            val count = feedbackDispatcher?.dispatchReport(reportJson) ?: 0
            showStatus("风险报告回放：执行 $count 条反馈")
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            startInference()
        } else {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startInference() {
        try {
            runtimeMetrics.reset()
            val model = OnnxYoloDetector(
                context = this,
                modelAsset = TwoWheelerRuntimeConfig.MODEL_ASSET,
                confidenceThreshold = TwoWheelerRuntimeConfig.CONFIDENCE,
                iouThreshold = TwoWheelerRuntimeConfig.NMS_IOU,
                inputSize = TwoWheelerRuntimeConfig.INPUT_SIZE,
            )
            val source = PhoneCameraFrameSource(this, this, previewView)
            val pipeline = InferencePipeline(
                detector = model,
                onResult = { result ->
                    runtimeMetrics.record(result.processingMs, result.droppedSinceLast)
                    val metrics = runtimeMetrics.snapshot()
                    val alerts = riskEngine.update(result)
                    val tracks = riskEngine.currentTracks
                    val region = walkableRegionEstimator.estimate(result)
                    val guidance = guidanceEngine.update(result, region, tracks, alerts)
                    runOnUiThread {
                        alerts.sortedBy { it.feedback.priority.ordinal }.forEach { alert ->
                            feedbackDispatcher?.dispatch(alert.trackId, alert.feedback)
                        }
                        guidance.feedback?.let { feedback ->
                            feedbackDispatcher?.dispatch("guidance", feedback)
                        }
                        trajectoryOverlay?.submit(result, tracks, guidance.state)
                        val alertText = if (alerts.isEmpty()) "" else " · 告警 ${alerts.size}"
                        val motionText = if (result.backgroundMotion?.reliable == true) "背景平移补偿" else "背景补偿不可用"
                        val guidanceText = guidanceLabel(guidance.state)
                        showStatus(
                                "运行中 · ${model.backendName}\n" +
                                "帧 ${result.sourceFrame} · 检测 ${result.detections.size} 个目标$alertText\n" +
                                "引路：$guidanceText · ${guidance.reason}\n" +
                                "FPS ${"%.1f".format(metrics.fps)} · " +
                                "推理 ${result.processingMs}ms · P95 ${metrics.p95ProcessingMs}ms\n" +
                                "丢帧 ${metrics.droppedFrames} · $motionText",
                        )
                    }
                },
                onError = { error ->
                    runOnUiThread { showStatus("推理错误：${error.message ?: "unknown"}") }
                },
            )
            detector = model
            cameraSource = source
            source.start(pipeline::onFrame)
            showStatus("正在启动本地模型…")
        } catch (error: Throwable) {
            showStatus("启动失败：${error.message ?: "unknown"}")
        }
    }

    private fun showStatus(text: String) {
        statusText?.text = text
    }

    private fun runFeedbackSelfTest() {
        val action = FeedbackAction.fromContract(
            priority = "warning",
            vibrationMs = listOf(120, 70, 120),
            tone = "warning",
            speech = "BlindNav 反馈自检",
            speechDelayMs = 250,
        ) ?: return
        feedbackDispatcher?.dispatch("self-test", action)
        showStatus("反馈自检：应出现两段震动、提示音和语音")
    }

    override fun onDestroy() {
        cameraSource?.stop()
        detector?.close()
        feedbackDispatcher?.close()
        riskEngine.reset()
        guidanceEngine.reset()
        runtimeMetrics.reset()
        trajectoryOverlay?.clearOverlay()
        cameraSource = null
        detector = null
        feedbackDispatcher = null
        previewView = null
        trajectoryOverlay = null
        super.onDestroy()
    }

    private fun guidanceLabel(state: GuidanceState): String = when (state) {
        GuidanceState.KEEP_STRAIGHT -> "保持直行"
        GuidanceState.MOVE_LEFT -> "向左绕行"
        GuidanceState.MOVE_RIGHT -> "向右绕行"
        GuidanceState.STOP -> "停止"
        GuidanceState.CAUTION -> "注意"
        GuidanceState.DANGER -> "危险"
        GuidanceState.UNKNOWN_SLOW_DOWN -> "前方不明，请减速"
    }

    companion object {
        const val EXTRA_RISK_REPORT_JSON = "blindnav.risk_report_json"
    }
}
