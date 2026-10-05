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
    val droppedSinceLast: Int = 0,
    val detections: List<Detection>,
    val backgroundMotion: BackgroundMotion? = null,
)

class InferencePipeline(
    private val detector: Detector,
    private val onResult: (FrameDetections) -> Unit,
    private val onError: (Throwable) -> Unit = {},
    private val motionEstimator: BackgroundMotionEstimator = BackgroundMotionEstimator(),
) {
    fun onFrame(packet: FramePacket) {
        val startedAtNs = System.nanoTime()
        try {
            val frame = packet.payload as? RgbFrame
                ?: error("Frame payload is not an owned RgbFrame")
            val detections = detector.detect(frame)
            val motion = motionEstimator.update(frame, packet.captureTsMs, detections)
            onResult(
                FrameDetections(
                    sourceFrame = packet.sourceFrame,
                    captureTsMs = packet.captureTsMs,
                    frameWidth = frame.width,
                    frameHeight = frame.height,
                    processingMs = ((System.nanoTime() - startedAtNs) / 1_000_000L).coerceAtLeast(0L),
                    droppedSinceLast = packet.droppedSinceLast,
                    detections = detections,
                    backgroundMotion = motion,
                ),
            )
        } catch (error: Throwable) {
            onError(error)
        }
    }
}
