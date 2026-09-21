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
import com.blindnav.mobile.feedback.FeedbackAction
import com.blindnav.mobile.feedback.FeedbackDispatcher
import com.blindnav.mobile.risk.TemporalRiskEngine
import com.blindnav.mobile.sensing.PhoneCameraFrameSource

/** Minimal shell; camera binding is intentionally kept behind FrameSource. */
class MainActivity : ComponentActivity() {
    private var cameraSource: PhoneCameraFrameSource? = null
    private var detector: OnnxYoloDetector? = null
    private var feedbackDispatcher: FeedbackDispatcher? = null
    private val riskEngine = TemporalRiskEngine()
    private var statusText: TextView? = null
    private var previewView: PreviewView? = null

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
        feedbackDispatcher = FeedbackDispatcher(this)
        findViewById<Button>(R.id.feedback_test_button).setOnClickListener {
            runFeedbackSelfTest()
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
            val model = OnnxYoloDetector(this)
            val source = PhoneCameraFrameSource(this, this, previewView)
            val pipeline = InferencePipeline(
                detector = model,
                onResult = { result ->
                    val alerts = riskEngine.update(result)
                    alerts.forEach { alert ->
                        feedbackDispatcher?.dispatch(alert.trackId, alert.feedback)
                    }
                    runOnUiThread {
                        val alertText = if (alerts.isEmpty()) "" else " · 告警 ${alerts.size}"
                        showStatus("运行中\n帧 ${result.sourceFrame} · 检测 ${result.detections.size} 个目标$alertText")
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
        cameraSource = null
        detector = null
        feedbackDispatcher = null
        previewView = null
        super.onDestroy()
    }
}
