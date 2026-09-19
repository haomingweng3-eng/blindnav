package com.blindnav.mobile.sensing

import android.content.Context
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import java.util.concurrent.Executor
import java.util.concurrent.Executors

/**
 * CameraX adapter for the default input path. It deliberately exposes an
 * ImageProxy as an opaque payload; the ONNX adapter owns pixel conversion.
 */
class PhoneCameraFrameSource(
    private val context: Context,
    private val lifecycleOwner: LifecycleOwner,
    private val executor: Executor = Executors.newSingleThreadExecutor(),
) : FrameSource {
    override val kind: SourceKind = SourceKind.PHONE_CAMERA

    private var cameraProvider: ProcessCameraProvider? = null
    private var analysis: ImageAnalysis? = null
    private var lastFrame: Long = -1L
    private var listener: ((FramePacket) -> Unit)? = null
    private val validator = FrameSequenceValidator()

    override fun start(listener: (FramePacket) -> Unit) {
        check(this.listener == null) { "Phone camera source is already running" }
        this.listener = listener

        val providerFuture = ProcessCameraProvider.getInstance(context)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val useCase = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
            useCase.setAnalyzer(executor) { image -> onImage(image) }

            provider.unbindAll()
            provider.bindToLifecycle(
                lifecycleOwner,
                CameraSelector.DEFAULT_BACK_CAMERA,
                useCase,
            )
            cameraProvider = provider
            analysis = useCase
        }, ContextCompat.getMainExecutor(context))
    }

    private fun onImage(image: ImageProxy) {
        val frame = if (lastFrame < 0) 0 else lastFrame + 1
        lastFrame = frame
        val timestampMs = image.imageInfo.timestamp / 1_000_000L
        val packet = FramePacket(
            source = SourceKind.PHONE_CAMERA,
            sourceFrame = frame,
            captureTsMs = timestampMs,
            width = image.width,
            height = image.height,
            transport = "camera2",
            // CameraX's KEEP_ONLY_LATEST strategy does not expose the exact
            // number of discarded frames; the transport adapter must report
            // it when the external protocol provides that information.
            droppedSinceLast = 0,
            payload = image,
        )
        try {
            val validation = validator.validate(packet)
            if (validation.accepted) {
                listener?.invoke(packet)
            }
        } finally {
            image.close()
        }
    }

    override fun stop() {
        analysis?.let { cameraProvider?.unbind(it) }
        cameraProvider = null
        analysis = null
        listener = null
        lastFrame = -1L
        validator.reset()
    }
}
