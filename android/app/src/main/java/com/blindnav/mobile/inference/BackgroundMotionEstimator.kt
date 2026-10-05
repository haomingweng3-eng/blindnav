package com.blindnav.mobile.inference

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/** Image displacement of the background, not vehicle velocity or metric pose. */
data class BackgroundMotion(
    val fromTimestampMs: Long,
    val toTimestampMs: Long,
    val dxPixels: Float = 0f,
    val dyPixels: Float = 0f,
    val reliable: Boolean = false,
    val matches: Int = 0,
    val inliers: Int = 0,
    val reason: String = "initial",
)

/**
 * Bounded, translation-only camera compensation without another model or native
 * dependency. Track textured background patches on an at-most-96px image.
 * Exclude current and previous detections, require forward/backward agreement,
 * unique patch matches and spatially distributed consensus. Rotation, zoom,
 * parallax, blur or insufficient texture can fail consensus: return unavailable,
 * never manufacture a zero-motion measurement in those cases.
 */
class BackgroundMotionEstimator {
    private data class Image(val width: Int, val height: Int, val gray: IntArray)
    private data class Previous(val image: Image, val timestamp: Long, val boxes: List<FloatArray>, val width: Int, val height: Int)
    private data class Match(val x: Int, val y: Int, val dx: Float, val dy: Float)
    private data class Search(val x: Int, val y: Int, val dx: Float, val dy: Float)
    private var previous: Previous? = null

    fun update(frame: RgbFrame, timestampMs: Long, detections: List<Detection>): BackgroundMotion =
        updateGray(downsample(frame), frame.width, frame.height, timestampMs, detections)

    /** Exact replay seam: recording uses the same 2x2 RGB luminance sampler. */
    fun updateRecordedGray(width: Int, height: Int, gray: ByteArray, frameWidth: Int, frameHeight: Int,
                           timestampMs: Long, detections: List<Detection>): BackgroundMotion {
        require(width > 0 && height > 0 && max(width, height) <= MAX_SIZE && gray.size == width * height)
        return updateGray(Image(width, height, IntArray(gray.size) { gray[it].toInt() and 255 }),
            frameWidth, frameHeight, timestampMs, detections)
    }

    fun reset() { previous = null }

    private fun updateGray(image: Image, frameWidth: Int, frameHeight: Int, timestampMs: Long,
                           detections: List<Detection>): BackgroundMotion {
        val old = previous
        val boxes = detections.filter { it.confidence >= 0.1f && validBox(it.box) }.map { it.box.copyOf() }
        previous = Previous(image, timestampMs, boxes, frameWidth, frameHeight)
        fun unavailable(reason: String, matches: Int = 0, inliers: Int = 0) =
            BackgroundMotion(old?.timestamp ?: timestampMs, timestampMs, matches = matches, inliers = inliers, reason = reason)
        if (old == null) return unavailable("initial")
        if (old.width != frameWidth || old.height != frameHeight || old.image.width != image.width || old.image.height != image.height)
            return unavailable("dimensions_changed")
        if (timestampMs - old.timestamp !in 1..750) return unavailable("timestamp_gap")
        if (min(image.width, image.height) < 32) return unavailable("image_too_small")
        val matches = mutableListOf<Match>()
        val margin = SEARCH_RADIUS + PATCH_RADIUS + 1
        for (row in 0 until GRID_ROWS) for (col in 0 until GRID_COLS) {
            val x0 = margin + (image.width - margin * 2) * col / GRID_COLS
            val x1 = margin + (image.width - margin * 2) * (col + 1) / GRID_COLS
            val y0 = margin + (image.height - margin * 2) * row / GRID_ROWS
            val y1 = margin + (image.height - margin * 2) * (row + 1) / GRID_ROWS
            var bestX = -1; var bestY = -1; var texture = 0f
            for (y in y0 until y1 step 3) for (x in x0 until x1 step 3) {
                if (masked(x, y, old.boxes, old.width, old.height, image, PATCH_RADIUS)) continue
                val variance = variance(old.image, x, y)
                if (variance > texture) { texture = variance; bestX = x; bestY = y }
            }
            if (bestX < 0 || texture < 80f) continue
            val forward = search(old.image, image, bestX, bestY, bestX, bestY) ?: continue
            if (masked(forward.x, forward.y, boxes, frameWidth, frameHeight, image, PATCH_RADIUS)) continue
            val backward = search(image, old.image, forward.x, forward.y, forward.x, forward.y) ?: continue
            if (abs(backward.x - bestX) > 1 || abs(backward.y - bestY) > 1) continue
            matches += Match(bestX, bestY, forward.dx, forward.dy)
        }
        if (matches.size < 8) return unavailable("insufficient_matches", matches.size)
        val dx = median(matches.map { it.dx }); val dy = median(matches.map { it.dy })
        val inliers = matches.filter { abs(it.dx - dx) <= 1.25f && abs(it.dy - dy) <= 1.25f }
        if (inliers.size < 8 || inliers.size < matches.size * 0.65f)
            return unavailable("inconsistent_background", matches.size, inliers.size)
        val spanX = inliers.maxOf { it.x } - inliers.minOf { it.x }
        val spanY = inliers.maxOf { it.y } - inliers.minOf { it.y }
        if (spanX < image.width * 0.3f || spanY < image.height * 0.2f)
            return unavailable("insufficient_coverage", matches.size, inliers.size)
        return BackgroundMotion(old.timestamp, timestampMs,
            median(inliers.map { it.dx }) * frameWidth / image.width,
            median(inliers.map { it.dy }) * frameHeight / image.height,
            true, matches.size, inliers.size, "translation_consensus")
    }

    private fun search(one: Image, two: Image, x: Int, y: Int, seedX: Int, seedY: Int): Search? {
        val costs = FloatArray((SEARCH_RADIUS * 2 + 1) * (SEARCH_RADIUS * 2 + 1)) { Float.POSITIVE_INFINITY }
        val side = SEARCH_RADIUS * 2 + 1
        val mean = mean(one, x, y)
        var best = Float.POSITIVE_INFINITY; var bestDx = 0; var bestDy = 0
        for (dy in -SEARCH_RADIUS..SEARCH_RADIUS) for (dx in -SEARCH_RADIUS..SEARCH_RADIUS) {
            val tx = seedX + dx; val ty = seedY + dy
            if (tx < PATCH_RADIUS || ty < PATCH_RADIUS || tx >= two.width - PATCH_RADIUS || ty >= two.height - PATCH_RADIUS) continue
            val targetMean = mean(two, tx, ty)
            var error = 0f
            for (py in -PATCH_RADIUS..PATCH_RADIUS) for (px in -PATCH_RADIUS..PATCH_RADIUS) {
                error += abs((one.gray[(y + py) * one.width + x + px] - mean) -
                    (two.gray[(ty + py) * two.width + tx + px] - targetMean))
            }
            error /= PATCH_SAMPLES
            costs[(dy + SEARCH_RADIUS) * side + dx + SEARCH_RADIUS] = error
            if (error < best) { best = error; bestDx = dx; bestDy = dy }
        }
        if (best > 18f || abs(bestDx) == SEARCH_RADIUS || abs(bestDy) == SEARCH_RADIUS) return null
        var second = Float.POSITIVE_INFINITY
        for (dy in -SEARCH_RADIUS..SEARCH_RADIUS) for (dx in -SEARCH_RADIUS..SEARCH_RADIUS) {
            if (abs(dx - bestDx) <= 1 && abs(dy - bestDy) <= 1) continue
            second = min(second, costs[(dy + SEARCH_RADIUS) * side + dx + SEARCH_RADIUS])
        }
        if (second < best * 1.3f + 2f) return null
        val index = (bestDy + SEARCH_RADIUS) * side + bestDx + SEARCH_RADIUS
        fun subpixel(left: Float, right: Float): Float {
            val denominator = left + right - best * 2
            return if (!denominator.isFinite() || denominator <= 0f) 0f else ((left - right) / (2 * denominator)).coerceIn(-0.5f, 0.5f)
        }
        return Search(seedX + bestDx, seedY + bestDy,
            seedX + bestDx - x + subpixel(costs[index - 1], costs[index + 1]),
            seedY + bestDy - y + subpixel(costs[index - side], costs[index + side]))
    }

    private fun variance(image: Image, x: Int, y: Int): Float {
        val mean = mean(image, x, y)
        var variance = 0f
        for (dy in -PATCH_RADIUS..PATCH_RADIUS) for (dx in -PATCH_RADIUS..PATCH_RADIUS) {
            val value = image.gray[(y + dy) * image.width + x + dx] - mean
            variance += value * value
        }
        return variance / PATCH_SAMPLES
    }

    private fun mean(image: Image, x: Int, y: Int): Float {
        var sum = 0
        for (dy in -PATCH_RADIUS..PATCH_RADIUS) for (dx in -PATCH_RADIUS..PATCH_RADIUS)
            sum += image.gray[(y + dy) * image.width + x + dx]
        return sum.toFloat() / PATCH_SAMPLES
    }

    private fun masked(x: Int, y: Int, boxes: List<FloatArray>, width: Int, height: Int, image: Image, radius: Int): Boolean =
        boxes.any { box ->
            x + radius >= box[0] * image.width / width - 2 && x - radius <= box[2] * image.width / width + 2 &&
                y + radius >= box[1] * image.height / height - 2 && y - radius <= box[3] * image.height / height + 2
        }

    private fun downsample(frame: RgbFrame): Image {
        require(frame.width > 0 && frame.height > 0 && frame.rgb.size == frame.width * frame.height * 3)
        val ratio = min(1f, MAX_SIZE.toFloat() / max(frame.width, frame.height))
        val width = max(1, (frame.width * ratio).roundToInt()); val height = max(1, (frame.height * ratio).roundToInt())
        val gray = IntArray(width * height)
        for (y in 0 until height) for (x in 0 until width) {
            var sum = 0
            for (oy in 0..1) for (ox in 0..1) {
                val sx = ((x + 0.25f + ox * 0.5f) * frame.width / width).toInt().coerceAtMost(frame.width - 1)
                val sy = ((y + 0.25f + oy * 0.5f) * frame.height / height).toInt().coerceAtMost(frame.height - 1)
                val index = (sy * frame.width + sx) * 3
                sum += (77 * (frame.rgb[index].toInt() and 255) + 150 * (frame.rgb[index + 1].toInt() and 255) +
                    29 * (frame.rgb[index + 2].toInt() and 255)) shr 8
            }
            gray[y * width + x] = sum / 4
        }
        return Image(width, height, gray)
    }

    private fun validBox(box: FloatArray) = box.size == 4 && box.all { it.isFinite() } && box[2] > box[0] && box[3] > box[1]
    private fun median(values: List<Float>): Float {
        val sorted = values.sorted(); val mid = sorted.size / 2
        return if (sorted.size % 2 == 0) (sorted[mid - 1] + sorted[mid]) / 2f else sorted[mid]
    }
    private companion object {
        // Keep the compensation budget below a fraction of a 320 model pass.
        const val MAX_SIZE = 96
        const val SEARCH_RADIUS = 6
        const val PATCH_RADIUS = 2
        const val PATCH_SAMPLES = 25f
        const val GRID_ROWS = 4
        const val GRID_COLS = 6
    }
}
