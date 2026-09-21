package com.blindnav.mobile.inference

import com.blindnav.mobile.sensing.FramePacket

fun interface Detector {
    fun detect(frame: RgbFrame): List<Detection>
}

data class FrameDetections(
    val sourceFrame: Long,
    val captureTsMs: Long,
    val frameWidth: Int,
    val frameHeight: Int,
    val detections: List<Detection>,
)

class InferencePipeline(
    private val detector: Detector,
    private val onResult: (FrameDetections) -> Unit,
    private val onError: (Throwable) -> Unit = {},
) {
    fun onFrame(packet: FramePacket) {
        try {
            val frame = packet.payload as? RgbFrame
                ?: error("Frame payload is not an owned RgbFrame")
            val detections = detector.detect(frame)
            onResult(
                FrameDetections(
                    sourceFrame = packet.sourceFrame,
                    captureTsMs = packet.captureTsMs,
                    frameWidth = frame.width,
                    frameHeight = frame.height,
                    detections = detections,
                ),
            )
        } catch (error: Throwable) {
            onError(error)
        }
    }
}
