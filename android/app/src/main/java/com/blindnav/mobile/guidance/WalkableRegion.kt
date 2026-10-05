package com.blindnav.mobile.guidance

import com.blindnav.mobile.inference.Detection
import com.blindnav.mobile.inference.FrameDetections
import kotlin.math.max

/** A normalized local free-space estimate. It is deliberately replaceable by a segmentation model. */
data class WalkableRegion(
    val left: Float,
    val right: Float,
    val floorY: Float,
    val confidence: Float,
    val source: String,
    val suggestedDirection: GuidanceState = GuidanceState.KEEP_STRAIGHT,
) {
    init {
        require(left in 0f..1f && right in 0f..1f && left < right)
        require(floorY in 0f..1f)
        require(confidence in 0f..1f)
    }

    fun containsContact(x: Float, y: Float): Boolean =
        x in left..right && y >= floorY
}

fun interface WalkableRegionEstimator {
    fun estimate(frame: FrameDetections): WalkableRegion
}

/**
 * Conservative phone fallback used until a learned walkable-area model is
 * available. It treats the lower central image as the local route and uses
 * detected contact points to choose an open side. It never claims metric
 * distance or sidewalk semantics.
 */
class GeometryWalkableRegionEstimator(
    private val baseLeft: Float = 0.36f,
    private val baseRight: Float = 0.64f,
    private val floorY: Float = 0.48f,
) : WalkableRegionEstimator {
    override fun estimate(frame: FrameDetections): WalkableRegion {
        val width = frame.frameWidth.toFloat().coerceAtLeast(1f)
        val height = frame.frameHeight.toFloat().coerceAtLeast(1f)
        val blockers = frame.detections.filter { detection ->
            valid(detection.box) && detection.confidence >= MIN_BLOCKER_CONFIDENCE &&
                detection.box[3] / height >= floorY
        }
        val leftCost = blockers.fold(0f) { total, item -> total + overlapCost(item, 0.12f, 0.40f, width) }
        val centerCost = blockers.fold(0f) { total, item -> total + overlapCost(item, baseLeft, baseRight, width) }
        val rightCost = blockers.fold(0f) { total, item -> total + overlapCost(item, 0.60f, 0.88f, width) }
        val centralBlocked = centerCost >= CENTER_BLOCK_COST
        val direction = when {
            !centralBlocked -> GuidanceState.KEEP_STRAIGHT
            leftCost + SIDE_MARGIN < rightCost -> GuidanceState.MOVE_LEFT
            rightCost + SIDE_MARGIN < leftCost -> GuidanceState.MOVE_RIGHT
            else -> GuidanceState.STOP
        }
        val confidence = if (blockers.isEmpty()) 0.55f else 0.45f
        return WalkableRegion(
            left = baseLeft,
            right = baseRight,
            floorY = floorY,
            confidence = confidence,
            source = "geometry_fallback",
            suggestedDirection = direction,
        )
    }

    private fun overlapCost(detection: Detection, left: Float, right: Float, width: Float): Float {
        val x1 = detection.box[0] / width
        val x2 = detection.box[2] / width
        val overlap = max(0f, minOf(x2, right) - maxOf(x1, left))
        return overlap * detection.confidence
    }

    private fun valid(box: FloatArray): Boolean =
        box.size == 4 && box.all { it.isFinite() } && box[2] > box[0] && box[3] > box[1]

    private companion object {
        const val MIN_BLOCKER_CONFIDENCE = 0.25f
        const val CENTER_BLOCK_COST = 0.08f
        const val SIDE_MARGIN = 0.04f
    }
}
