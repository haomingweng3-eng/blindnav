package com.blindnav.mobile.guidance

import com.blindnav.mobile.inference.Detection
import com.blindnav.mobile.inference.FrameDetections
import com.blindnav.mobile.inference.RgbFrame
import kotlin.math.sqrt

/**
 * Small phone-side free-space fallback.
 *
 * This is deliberately a local surface continuity estimator, not a semantic
 * segmentation model. It only authorizes a direction when the lower image has
 * a consistent surface colour and the detector has not occupied that
 * corridor. Otherwise the guidance engine remains in UNKNOWN_SLOW_DOWN.
 */
class RgbWalkableRegionEstimator(
    private val routeLeft: Float = 0.36f,
    private val routeRight: Float = 0.64f,
    // Contact points around the middle of a 16:9 frame can already be on the
    // road for a distant incoming rider. Keep this aligned with the desktop
    // route corridor; RGB surface sampling still starts lower at y=0.62.
    private val floorY: Float = 0.48f,
) : WalkableRegionEstimator {
    override fun estimate(frame: FrameDetections): WalkableRegion {
        val rgb = frame.rgbFrame ?: return fallback(frame)
        if (rgb.width != frame.frameWidth || rgb.height != frame.frameHeight ||
            rgb.rgb.size < rgb.width * rgb.height * 3
        ) return fallback(frame)

        val reference = referenceColour(rgb, frame.detections)
        val forward = corridorSupport(rgb, frame.detections, 0.36f, 0.64f, 0.40f, 0.60f, reference)
        // Side corridors stay outside the central walking corridor at the
        // bottom of the image; otherwise their perspective taper would
        // overlap the same pixels and falsely erase a valid detour.
        val left = corridorSupport(rgb, frame.detections, 0.12f, 0.35f, 0.12f, 0.35f, reference)
        val right = corridorSupport(rgb, frame.detections, 0.65f, 0.88f, 0.65f, 0.88f, reference)
        val strongest = maxOf(forward, left, right)
        val confidence = (strongest * if (strongest >= 0.70f) 1.0f else 0.75f)
            .coerceIn(0f, 1f)
        val surface = if (strongest >= 0.70f) "local_surface" else "unknown"
        return WalkableRegion(
            left = routeLeft,
            right = routeRight,
            floorY = floorY,
            confidence = confidence,
            source = "rgb_surface",
            suggestedDirection = GuidanceState.UNKNOWN_SLOW_DOWN,
            forwardSupport = forward,
            leftSupport = left,
            rightSupport = right,
            surface = surface,
        )
    }

    private fun fallback(frame: FrameDetections): WalkableRegion =
        GeometryWalkableRegionEstimator(routeLeft, routeRight, floorY).estimate(frame)

    private fun referenceColour(rgb: RgbFrame, detections: List<Detection>): IntArray {
        var red = 0L
        var green = 0L
        var blue = 0L
        var count = 0
        for (row in 0 until 4) {
            val y = (rgb.height * (0.90f + row * 0.02f)).toInt().coerceIn(0, rgb.height - 1)
            for (column in 0 until 8) {
                val x = (rgb.width * (0.44f + column * 0.017f)).toInt().coerceIn(0, rgb.width - 1)
                val nx = x.toFloat() / rgb.width
                val ny = y.toFloat() / rgb.height
                if (insideDetection(nx, ny, detections, rgb.width, rgb.height)) continue
                val offset = (y * rgb.width + x) * 3
                red += rgb.rgb[offset].toInt() and 0xff
                green += rgb.rgb[offset + 1].toInt() and 0xff
                blue += rgb.rgb[offset + 2].toInt() and 0xff
                count++
            }
        }
        if (count == 0) {
            val x = (rgb.width * 0.50f).toInt().coerceIn(0, rgb.width - 1)
            val y = (rgb.height * 0.92f).toInt().coerceIn(0, rgb.height - 1)
            val offset = (y * rgb.width + x) * 3
            return intArrayOf(rgb.rgb[offset].toInt() and 0xff,
                rgb.rgb[offset + 1].toInt() and 0xff, rgb.rgb[offset + 2].toInt() and 0xff)
        }
        return intArrayOf((red / count).toInt(), (green / count).toInt(), (blue / count).toInt())
    }

    private fun corridorSupport(
        rgb: RgbFrame,
        detections: List<Detection>,
        topLeft: Float,
        topRight: Float,
        bottomLeft: Float,
        bottomRight: Float,
        reference: IntArray,
    ): Float {
        var supported = 0
        var total = 0
        for (row in 0 until 8) {
            val progress = (row + 0.5f) / 8f
            val y = 0.62f + progress * 0.34f
            val left = topLeft + (bottomLeft - topLeft) * progress
            val right = topRight + (bottomRight - topRight) * progress
            for (column in 0 until 6) {
                val x = left + (column + 0.5f) / 6f * (right - left)
                total++
                if (insideDetection(x, y, detections, rgb.width, rgb.height)) continue
                val pixel = pixel(rgb, x, y)
                if (colourDistance(pixel, reference) <= COLOUR_TOLERANCE) supported++
            }
        }
        return if (total == 0) 0f else supported.toFloat() / total
    }

    private fun insideDetection(x: Float, y: Float, detections: List<Detection>, width: Int, height: Int): Boolean =
        detections.any { detection ->
            val box = detection.box
            if (box.size != 4 || box.any { !it.isFinite() } || box[2] <= box[0] || box[3] <= box[1]) {
                false
            } else {
                val left = box[0] / width
                val top = box[1] / height
                val right = box[2] / width
                // The pixels behind an object are occluded. Treat the whole
                // lower continuation of its horizontal footprint as unknown;
                // otherwise a central target could still appear to leave a
                // clear path simply because its box ends above the bottom row.
                x in left..right && y >= minOf(top, floorY)
            }
        }

    private fun pixel(rgb: RgbFrame, x: Float, y: Float): IntArray {
        val px = (x * rgb.width).toInt().coerceIn(0, rgb.width - 1)
        val py = (y * rgb.height).toInt().coerceIn(0, rgb.height - 1)
        val offset = (py * rgb.width + px) * 3
        return intArrayOf(rgb.rgb[offset].toInt() and 0xff,
            rgb.rgb[offset + 1].toInt() and 0xff, rgb.rgb[offset + 2].toInt() and 0xff)
    }

    private fun colourDistance(left: IntArray, right: IntArray): Float {
        val dr = (left[0] - right[0]).toFloat()
        val dg = (left[1] - right[1]).toFloat()
        val db = (left[2] - right[2]).toFloat()
        return sqrt(dr * dr + dg * dg + db * db)
    }

    private companion object {
        const val COLOUR_TOLERANCE = 58f
    }
}
