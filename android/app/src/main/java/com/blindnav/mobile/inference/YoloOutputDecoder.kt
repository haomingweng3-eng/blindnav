package com.blindnav.mobile.inference

import kotlin.math.max
import kotlin.math.min

data class Detection(
    val classId: Int,
    val confidence: Float,
    /** x1, y1, x2, y2 in original image pixels. */
    val box: FloatArray,
)

/** Decodes YOLOv8 [1, 84, N] channel-major output and applies class-wise NMS. */
object YoloOutputDecoder {
    fun decode(
        raw: FloatArray,
        candidates: Int,
        originalWidth: Int,
        originalHeight: Int,
        ratio: Float,
        padLeft: Float,
        padTop: Float,
        confidenceThreshold: Float = 0.25f,
        iouThreshold: Float = 0.7f,
    ): List<Detection> {
        require(candidates > 0)
        require(originalWidth > 0 && originalHeight > 0)
        require(ratio > 0f)
        require(raw.size >= 5 * candidates)
        require(raw.size % candidates == 0)

        val channels = raw.size / candidates
        val classCount = channels - 4
        val selected = mutableListOf<Detection>()
        for (candidate in 0 until candidates) {
            var bestClass = -1
            var bestScore = Float.NEGATIVE_INFINITY
            for (classId in 0 until classCount) {
                val score = raw[(4 + classId) * candidates + candidate]
                if (score > bestScore) {
                    bestScore = score
                    bestClass = classId
                }
            }
            if (bestScore < confidenceThreshold) continue

            val cx = raw[0 * candidates + candidate]
            val cy = raw[1 * candidates + candidate]
            val width = raw[2 * candidates + candidate]
            val height = raw[3 * candidates + candidate]
            val x1 = ((cx - width / 2f - padLeft) / ratio).coerceIn(0f, originalWidth.toFloat())
            val y1 = ((cy - height / 2f - padTop) / ratio).coerceIn(0f, originalHeight.toFloat())
            val x2 = ((cx + width / 2f - padLeft) / ratio).coerceIn(0f, originalWidth.toFloat())
            val y2 = ((cy + height / 2f - padTop) / ratio).coerceIn(0f, originalHeight.toFloat())
            if (x2 <= x1 || y2 <= y1) continue
            selected += Detection(bestClass, bestScore, floatArrayOf(x1, y1, x2, y2))
        }

        val kept = mutableListOf<Detection>()
        for ((_, sameClass) in selected.groupBy { it.classId }) {
            val remaining = sameClass.sortedByDescending { it.confidence }.toMutableList()
            while (remaining.isNotEmpty()) {
                val best = remaining.removeAt(0)
                kept += best
                remaining.removeAll { iou(best.box, it.box) > iouThreshold }
            }
        }
        return kept.sortedByDescending { it.confidence }
    }

    private fun iou(one: FloatArray, two: FloatArray): Float {
        val left = max(one[0], two[0])
        val top = max(one[1], two[1])
        val right = min(one[2], two[2])
        val bottom = min(one[3], two[3])
        val intersection = max(0f, right - left) * max(0f, bottom - top)
        val areaOne = max(0f, one[2] - one[0]) * max(0f, one[3] - one[1])
        val areaTwo = max(0f, two[2] - two[0]) * max(0f, two[3] - two[1])
        val union = areaOne + areaTwo - intersection
        return if (union <= 0f) 0f else intersection / union
    }
}
