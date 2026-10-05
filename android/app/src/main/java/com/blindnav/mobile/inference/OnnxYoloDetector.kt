package com.blindnav.mobile.inference

import android.content.Context
import android.util.Log
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ai.onnxruntime.TensorInfo
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Single-threaded adapter for fixed-size YOLO channel-major outputs. */
class OnnxYoloDetector(
    context: Context,
    modelAsset: String = "yolov8n.onnx",
    private val confidenceThreshold: Float = 0.25f,
    private val iouThreshold: Float = 0.7f,
    private val inputSize: Int = 640,
) : Detector, AutoCloseable {
    private val environment = OrtEnvironment.getEnvironment()
    private val sessionHandle: SessionHandle
    private val session: OrtSession
    private val inputName: String
    private val inputTensor: OnnxTensor
    private val chw = FloatArray(3 * inputSize * inputSize)
    private val inputBuffer = ByteBuffer.allocateDirect(chw.size * 4).order(ByteOrder.nativeOrder()).asFloatBuffer()
    private val outputBuffer: FloatArray
    private val candidates: Int
    private val preprocessor = LetterboxPreprocessor(targetSize = inputSize, paddingValue = 114f / 255f)

    init {
        require(inputSize > 0) { "inputSize must be positive" }
    }

    /** The provider selected at construction time, including CPU fallback. */
    val backendName: String
        get() = sessionHandle.backendName

    init {
        val modelBytes = context.assets.open(modelAsset).use { it.readBytes() }
        sessionHandle = createSession(modelBytes)
        session = sessionHandle.session
        inputName = session.inputNames.single()
        require(session.outputInfo.size == 1) { "YOLO model must expose one output tensor" }
        val inputShape = (session.inputInfo.getValue(inputName).info as TensorInfo).shape
        require(inputShape.contentEquals(longArrayOf(1, 3, inputSize.toLong(), inputSize.toLong()))) {
            "Model input shape does not match inputSize=$inputSize"
        }
        val outputShape = (session.outputInfo.values.single().info as TensorInfo).shape
        require(outputShape.size == 3 && outputShape[0] == 1L && outputShape[1] >= 5 && outputShape[2] > 0) {
            "Expected fixed YOLO output [1,channels,candidates]"
        }
        candidates = outputShape[2].toInt()
        outputBuffer = FloatArray((outputShape[1] * outputShape[2]).toInt())
        inputTensor = OnnxTensor.createTensor(environment, inputBuffer, inputShape)
        Log.i(TAG, "model=$modelAsset backend=$backendName")
    }

    @Synchronized
    override fun detect(frame: RgbFrame): List<Detection> {
        require(frame.rgb.size == frame.width * frame.height * 3)
        val prepared = preprocessor.convert(frame.rgb, frame.width, frame.height, chw)
        inputBuffer.rewind()
        inputBuffer.put(prepared.chw)
        inputBuffer.rewind()
            session.run(mapOf(inputName to inputTensor)).use { result ->
                (result[0] as OnnxTensor).floatBuffer.get(outputBuffer)
                return YoloOutputDecoder.decode(
                    raw = outputBuffer,
                    candidates = candidates,
                    originalWidth = frame.width,
                    originalHeight = frame.height,
                    ratio = prepared.scale,
                    padLeft = prepared.padLeft.toFloat(),
                    padTop = prepared.padTop.toFloat(),
                    confidenceThreshold = confidenceThreshold,
                    iouThreshold = iouThreshold,
                )
            }
    }

    @Synchronized
    override fun close() {
        inputTensor.close()
        session.close()
    }

    private fun createSession(modelBytes: ByteArray): SessionHandle {
        // XNNPACK is tried first because NNAPI often accepts a graph while
        // silently falling back for unsupported YOLO operators.  That fallback
        // can make live inference much slower than the predictable CPU path.
        // NNAPI remains an available fallback for devices with a complete
        // accelerator implementation.
        val attempts = listOf(
            "XNNPACK" to { options: OrtSession.SessionOptions -> options.addXnnpack(emptyMap()) },
            "NNAPI" to { options: OrtSession.SessionOptions -> options.addNnapi() },
            "CPU" to { _: OrtSession.SessionOptions -> },
        )
        var lastError: Throwable? = null
        for ((name, configure) in attempts) {
            val options = OrtSession.SessionOptions()
            try {
                options.setIntraOpNumThreads(CPU_THREADS)
                options.setInterOpNumThreads(1)
                configure(options)
                val session = environment.createSession(modelBytes, options)
                options.close()
                return SessionHandle(session, name)
            } catch (error: Throwable) {
                lastError = error
                try {
                    options.close()
                } catch (_: Throwable) {
                    // Preserve the provider failure as the useful diagnostic.
                }
            }
        }
        throw IllegalStateException("Unable to create ONNX session", lastError)
    }

    private data class SessionHandle(
        val session: OrtSession,
        val backendName: String,
    )

    private companion object {
        const val TAG = "BlindNav"
        const val CPU_THREADS = 4
    }
}
