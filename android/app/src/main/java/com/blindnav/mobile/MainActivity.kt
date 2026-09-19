package com.blindnav.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.blindnav.mobile.inference.InferencePipeline
import com.blindnav.mobile.inference.OnnxYoloDetector
import com.blindnav.mobile.sensing.PhoneCameraFrameSource

/** Minimal shell; camera binding is intentionally kept behind FrameSource. */
class MainActivity : ComponentActivity() {
    private var cameraSource: PhoneCameraFrameSource? = null
    private var detector: OnnxYoloDetector? = null
    private var statusText: TextView? = null

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) startInference() else showStatus("需要相机权限才能运行感知")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.status_text)
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
            val source = PhoneCameraFrameSource(this, this)
            val pipeline = InferencePipeline(
                detector = model,
                onResult = { result ->
                    runOnUiThread {
                        showStatus("运行中\n帧 ${result.sourceFrame} · 检测 ${result.detections.size} 个目标")
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

    override fun onDestroy() {
        cameraSource?.stop()
        detector?.close()
        cameraSource = null
        detector = null
        super.onDestroy()
    }
}
