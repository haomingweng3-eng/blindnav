package com.blindnav.mobile.inference

import android.content.Context
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.nio.FloatBuffer

/** Android ONNX Runtime adapter for the bundled YOLOv8n [1,3,640,640] model. */
class OnnxYoloDetector(
    context: Context,
    modelAsset: String = "yolov8n.onnx",
    private val confidenceThreshold: Float = 0.25f,
    private val iouThreshold: Float = 0.7f,
) : Detector, AutoCloseable {
    private val environment = OrtEnvironment.getEnvironment()
    private val session: OrtSession
    private val inputName: String
    private val preprocessor = LetterboxPreprocessor(targetSize = 640, paddingValue = 114f / 255f)

    init {
        val modelBytes = context.assets.open(modelAsset).use { it.readBytes() }
        session = environment.createSession(modelBytes, OrtSession.SessionOptions())
        inputName = session.inputNames.single()
        require(session.outputInfo.size == 1) { "YOLO model must expose one output tensor" }
    }

    override fun detect(frame: RgbFrame): List<Detection> {
        require(frame.rgb.size == frame.width * frame.height * 3)
        val prepared = preprocessor.convert(frame.rgb, frame.width, frame.height)
        val shape = longArrayOf(1, 3, 640, 640)
        OnnxTensor.createTensor(environment, FloatBuffer.wrap(prepared.chw), shape).use { input ->
            session.run(mapOf(inputName to input)).use { result ->
                val raw = flattenOutput(result[0].value)
                return YoloOutputDecoder.decode(
                    raw = raw,
                    candidates = 8400,
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
    }

    @Suppress("UNCHECKED_CAST")
    private fun flattenOutput(value: Any): FloatArray {
        val batches = value as? Array<Array<FloatArray>>
            ?: error("Expected YOLO output shaped [1,84,8400]")
        require(batches.size == 1)
        val channels = batches[0]
        require(channels.size == 84)
        require(channels.all { it.size == 8400 })
        return FloatArray(84 * 8400).also { output ->
            for (channel in channels.indices) {
                channels[channel].copyInto(output, destinationOffset = channel * 8400)
            }
        }
    }

    override fun close() {
        session.close()
    }
}
