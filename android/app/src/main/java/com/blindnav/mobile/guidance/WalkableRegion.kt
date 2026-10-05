package com.blindnav.mobile.guidance

import com.blindnav.mobile.inference.FrameDetections

/** A normalized local free-space estimate. It is deliberately replaceable by a segmentation model. */
data class WalkableRegion(
    val left: Float,
    val right: Float,
    val floorY: Float,
    val confidence: Float,
    val source: String,
    val suggestedDirection: GuidanceState = GuidanceState.KEEP_STRAIGHT,
    // Connected semantic surface support along an entire candidate corridor.
    // Absence of detections is not positive evidence of free space.
    val forwardSupport: Float = 0f,
    val leftSupport: Float = 0f,
    val rightSupport: Float = 0f,
    val surface: String = "unknown",
) {
    init {
        require(left in 0f..1f && right in 0f..1f && left < right)
        require(floorY in 0f..1f)
        require(confidence in 0f..1f)
        require(listOf(forwardSupport, leftSupport, rightSupport).all { it in 0f..1f })
    }

    fun containsContact(x: Float, y: Float): Boolean =
        x in left..right && y >= floorY

    val hasSurfaceEvidence: Boolean
        get() = source != "geometry_fallback" && surface != "unknown" && confidence >= 0.65f

    fun supportedDirection(): GuidanceState = when {
        !hasSurfaceEvidence -> GuidanceState.UNKNOWN_SLOW_DOWN
        // The central corridor may lose a few samples to detector boxes or
        // pavement seams. A high but not perfect support is acceptable only
        // after GuidanceEngine's temporal and motion checks.
        forwardSupport >= 0.80f -> GuidanceState.KEEP_STRAIGHT
        leftSupport >= 0.90f && rightSupport <= 0.65f -> GuidanceState.MOVE_LEFT
        rightSupport >= 0.90f && leftSupport <= 0.65f -> GuidanceState.MOVE_RIGHT
        else -> GuidanceState.UNKNOWN_SLOW_DOWN
    }
}

fun interface WalkableRegionEstimator {
    fun estimate(frame: FrameDetections): WalkableRegion
}

/**
 * Conservative phone fallback used until a learned walkable-area model is
 * available. It locates the intended central corridor for obstacle warnings.
 * It cannot verify the ground or either side and never authorizes a direction.
 */
class GeometryWalkableRegionEstimator(
    private val baseLeft: Float = 0.36f,
    private val baseRight: Float = 0.64f,
    private val floorY: Float = 0.48f,
) : WalkableRegionEstimator {
    override fun estimate(frame: FrameDetections): WalkableRegion {
        return WalkableRegion(
            left = baseLeft,
            right = baseRight,
            floorY = floorY,
            confidence = 0.25f,
            source = "geometry_fallback",
            suggestedDirection = GuidanceState.UNKNOWN_SLOW_DOWN,
        )
    }
}
