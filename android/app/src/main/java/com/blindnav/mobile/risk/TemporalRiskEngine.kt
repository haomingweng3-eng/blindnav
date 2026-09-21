package com.blindnav.mobile.risk

import com.blindnav.mobile.feedback.FeedbackAction
import com.blindnav.mobile.feedback.FeedbackPriority
import com.blindnav.mobile.inference.Detection
import com.blindnav.mobile.inference.FrameDetections
import kotlin.math.abs
import kotlin.math.ln

data class AndroidRiskAlert(
    val trackId: String,
    val className: String,
    val direction: String,
    val loomingPerSecond: Float,
    val feedback: FeedbackAction,
)

/**
 * Conservative Android MVP risk adapter for the live camera path.
 *
 * This is intentionally not presented as ByteTrack or a calibrated collision
 * predictor. It keeps one temporal state per supported COCO class, requires a
 * central target and a positive area-growth trend, and emits feedback only
 * after consecutive frames. The Python risk engine remains the experiment
 * reference until Android-side thresholds are calibrated on real footage.
 */
class TemporalRiskEngine(
    private val loomingThresholdPerSecond: Float = 2f,
    private val urgentThresholdPerSecond: Float = 5f,
    private val maxCenterJumpFraction: Float = 0.35f,
    private val cooldownMs: Long = 1_000L,
) {
    private data class State(
        val centerX: Float,
        val centerY: Float,
        val areaFraction: Float,
        val timestampMs: Long,
        val observations: Int,
        val lastAlertMs: Long,
    )

    private val states = mutableMapOf<Int, State>()

    fun update(frame: FrameDetections): List<AndroidRiskAlert> {
        require(frame.frameWidth > 0 && frame.frameHeight > 0)
        val output = mutableListOf<AndroidRiskAlert>()
        val imageArea = frame.frameWidth.toFloat() * frame.frameHeight.toFloat()
        val seenClasses = mutableSetOf<Int>()

        for (detection in frame.detections) {
            val className = CLASS_NAMES[detection.classId] ?: continue
            if (detection.confidence < MIN_CONFIDENCE || !validBox(detection.box)) continue
            val classId = detection.classId
            if (!seenClasses.add(classId)) continue

            val box = detection.box
            val centerX = (box[0] + box[2]) / 2f
            val centerY = (box[1] + box[3]) / 2f
            val areaFraction = ((box[2] - box[0]) * (box[3] - box[1])) / imageArea
            val previous = states[classId]
            val next = State(centerX, centerY, areaFraction, frame.captureTsMs, (previous?.observations ?: 0) + 1, previous?.lastAlertMs ?: Long.MIN_VALUE)
            states[classId] = next

            if (previous == null || previous.timestampMs >= frame.captureTsMs) continue
            val centerJump = distanceFraction(previous.centerX, previous.centerY, centerX, centerY, frame.frameWidth, frame.frameHeight)
            if (centerJump > maxCenterJumpFraction) continue
            val dtSeconds = (frame.captureTsMs - previous.timestampMs) / 1_000f
            if (dtSeconds <= 0f || previous.areaFraction <= 0f || areaFraction <= previous.areaFraction) continue
            if (centerX / frame.frameWidth !in WALKING_CORRIDOR) continue

            val looming = (ln(areaFraction / previous.areaFraction) / dtSeconds)
            if (looming < loomingThresholdPerSecond || next.observations < 2) continue
            if (previous.lastAlertMs != Long.MIN_VALUE &&
                frame.captureTsMs - previous.lastAlertMs < cooldownMs
            ) continue

            val priority = if (looming >= urgentThresholdPerSecond) FeedbackPriority.URGENT else FeedbackPriority.WARNING
            val direction = directionFor(centerX / frame.frameWidth)
            val feedback = FeedbackAction.fromContract(
                priority = priority.contractName,
                vibrationMs = if (priority == FeedbackPriority.URGENT) listOf(260, 80, 260) else listOf(120, 70, 120),
                tone = if (priority == FeedbackPriority.URGENT) "danger" else "warning",
                speech = if (priority == FeedbackPriority.URGENT) "危险，${directionName(direction)}${className}快速接近" else "注意，${directionName(direction)}$className",
                speechDelayMs = if (priority == FeedbackPriority.URGENT) 100 else 250,
            ) ?: continue
            states[classId] = next.copy(lastAlertMs = frame.captureTsMs)
            output += AndroidRiskAlert("${CLASS_KEYS[classId]}-$classId", className, direction, looming, feedback)
        }
        return output
    }

    fun reset() = states.clear()

    private fun validBox(box: FloatArray): Boolean =
        box.size == 4 && box[2] > box[0] && box[3] > box[1]

    private fun distanceFraction(x1: Float, y1: Float, x2: Float, y2: Float, width: Int, height: Int): Float {
        val dx = (x2 - x1) / width
        val dy = (y2 - y1) / height
        return kotlin.math.sqrt(dx * dx + dy * dy)
    }

    private fun directionFor(normalizedX: Float): String = when {
        normalizedX < 0.33f -> "left"
        normalizedX > 0.67f -> "right"
        else -> "front"
    }

    private fun directionName(direction: String): String = when (direction) {
        "left" -> "左侧"
        "right" -> "右侧"
        else -> "前方"
    }

    private companion object {
        const val MIN_CONFIDENCE = 0.25f
        val WALKING_CORRIDOR = 0.2f..0.8f
        val CLASS_NAMES = mapOf(0 to "行人", 1 to "自行车", 2 to "汽车", 3 to "摩托车", 5 to "公交车", 7 to "卡车")
        val CLASS_KEYS = mapOf(0 to "person", 1 to "bicycle", 2 to "car", 3 to "motorcycle", 5 to "bus", 7 to "truck")
        val FeedbackPriority.contractName: String
            get() = when (this) {
                FeedbackPriority.LOW -> "low"
                FeedbackPriority.WARNING -> "warning"
                FeedbackPriority.URGENT -> "urgent"
            }
    }
}
