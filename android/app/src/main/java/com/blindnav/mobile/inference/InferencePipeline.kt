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
    val processingMs: Long = 0L,
    val detections: List<Detection>,
)

class InferencePipeline(
    private val detector: Detector,
    private val onResult: (FrameDetections) -> Unit,
    private val onError: (Throwable) -> Unit = {},
) {
    fun onFrame(packet: FramePacket) {
        val startedAtNs = System.nanoTime()
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
                    processingMs = ((System.nanoTime() - startedAtNs) / 1_000_000L).coerceAtLeast(0L),
                    detections = detections,
                ),
            )
        } catch (error: Throwable) {
            onError(error)
        }
    }
}
