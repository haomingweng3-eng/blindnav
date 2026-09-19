package com.blindnav.mobile.inference

import kotlin.math.roundToInt

data class YuvPlane(
    val bytes: ByteArray,
    val rowStride: Int,
    val pixelStride: Int,
)

data class RgbFrame(
    val width: Int,
    val height: Int,
    val rgb: ByteArray,
)

/** Converts CameraX YUV_420_888 planes into an owned interleaved RGB buffer. */
object Yuv420RgbConverter {
    fun convert(
        width: Int,
        height: Int,
        y: YuvPlane,
        u: YuvPlane,
        v: YuvPlane,
    ): ByteArray {
        require(width > 0 && height > 0) { "image dimensions must be positive" }
        require(y.rowStride > 0 && y.pixelStride > 0)
        require(u.rowStride > 0 && u.pixelStride > 0)
        require(v.rowStride > 0 && v.pixelStride > 0)

        val rgb = ByteArray(width * height * 3)
        var output = 0
        for (row in 0 until height) {
            for (column in 0 until width) {
                val yValue = sample(y, column, row)
                val chromaColumn = column / 2
                val chromaRow = row / 2
                val uValue = sample(u, chromaColumn, chromaRow)
                val vValue = sample(v, chromaColumn, chromaRow)
                val chromaU = uValue - 128
                val chromaV = vValue - 128
                val red = yValue + 1.402f * chromaV
                val green = yValue - 0.344136f * chromaU - 0.714136f * chromaV
                val blue = yValue + 1.772f * chromaU
                rgb[output++] = clamp(red)
                rgb[output++] = clamp(green)
                rgb[output++] = clamp(blue)
            }
        }
        return rgb
    }

    private fun sample(plane: YuvPlane, column: Int, row: Int): Int {
        val index = row * plane.rowStride + column * plane.pixelStride
        require(index in plane.bytes.indices) { "YUV plane buffer is smaller than its strides" }
        return plane.bytes[index].toInt() and 0xFF
    }

    private fun clamp(value: Float): Byte = value.roundToInt().coerceIn(0, 255).toByte()
}
