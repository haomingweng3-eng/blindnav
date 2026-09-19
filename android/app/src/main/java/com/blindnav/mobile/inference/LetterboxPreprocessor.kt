package com.blindnav.mobile.inference

import kotlin.math.min
import kotlin.math.roundToInt

/** YOLO-compatible RGB letterbox preprocessing without Android Bitmap state. */
class LetterboxPreprocessor(
    private val targetSize: Int,
    private val paddingValue: Float = 0.5f,
) {
    init {
        require(targetSize > 0) { "targetSize must be positive" }
        require(paddingValue in 0f..1f) { "paddingValue must be in [0, 1]" }
    }

    fun convert(rgb: ByteArray, width: Int, height: Int): LetterboxResult {
        require(width > 0 && height > 0) { "source dimensions must be positive" }
        require(rgb.size == width * height * 3) {
            "RGB buffer must contain exactly width*height*3 bytes"
        }

        val scale = min(targetSize.toFloat() / width, targetSize.toFloat() / height)
        val scaledWidth = (width * scale).roundToInt().coerceAtLeast(1)
        val scaledHeight = (height * scale).roundToInt().coerceAtLeast(1)
        val padLeft = (targetSize - scaledWidth) / 2
        val padTop = (targetSize - scaledHeight) / 2
        val output = FloatArray(targetSize * targetSize * 3) { paddingValue }

        for (y in 0 until scaledHeight) {
            val sourceY = ((y / scale).toInt()).coerceIn(0, height - 1)
            for (x in 0 until scaledWidth) {
                val sourceX = ((x / scale).toInt()).coerceIn(0, width - 1)
                val sourceBase = (sourceY * width + sourceX) * 3
                val targetX = x + padLeft
                val targetY = y + padTop
                for (channel in 0..2) {
                    val value = (rgb[sourceBase + channel].toInt() and 0xFF) / 255f
                    output[(channel * targetSize * targetSize) + targetY * targetSize + targetX] = value
                }
            }
        }

        return LetterboxResult(
            chw = output,
            targetSize = targetSize,
            scale = scale,
            scaledWidth = scaledWidth,
            scaledHeight = scaledHeight,
            padLeft = padLeft,
            padTop = padTop,
        )
    }
}

data class LetterboxResult(
    val chw: FloatArray,
    val targetSize: Int,
    val scale: Float,
    val scaledWidth: Int,
    val scaledHeight: Int,
    val padLeft: Int,
    val padTop: Int,
) {
    fun rgbIndex(x: Int, y: Int, channel: Int): Int {
        require(x in 0 until targetSize)
        require(y in 0 until targetSize)
        require(channel in 0..2)
        return channel * targetSize * targetSize + y * targetSize + x
    }
}
