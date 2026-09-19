package com.blindnav.mobile.inference

import org.junit.Assert.assertEquals
import org.junit.Test

class Yuv420RgbConverterTest {
    @Test
    fun convertsNeutralTwoByTwoFrameToGrayRgb() {
        val y = byteArrayOf(128.toByte(), 128.toByte(), 128.toByte(), 128.toByte())
        val u = byteArrayOf(128.toByte())
        val v = byteArrayOf(128.toByte())

        val rgb = Yuv420RgbConverter.convert(
            width = 2,
            height = 2,
            y = YuvPlane(y, rowStride = 2, pixelStride = 1),
            u = YuvPlane(u, rowStride = 1, pixelStride = 1),
            v = YuvPlane(v, rowStride = 1, pixelStride = 1),
        )

        assertEquals(12, rgb.size)
        assertEquals(128, rgb[0].toInt() and 0xFF)
        assertEquals(128, rgb[1].toInt() and 0xFF)
        assertEquals(128, rgb[2].toInt() and 0xFF)
    }

    @Test
    fun respectsPlaneRowAndPixelStrides() {
        val y = byteArrayOf(100.toByte(), 0, 100.toByte(), 0, 100.toByte(), 0, 100.toByte(), 0)
        val u = byteArrayOf(128.toByte(), 0, 128.toByte(), 0)
        val v = byteArrayOf(128.toByte(), 0, 128.toByte(), 0)

        val rgb = Yuv420RgbConverter.convert(
            width = 2,
            height = 2,
            y = YuvPlane(y, rowStride = 4, pixelStride = 2),
            u = YuvPlane(u, rowStride = 4, pixelStride = 2),
            v = YuvPlane(v, rowStride = 4, pixelStride = 2),
        )

        assertEquals(100, rgb[0].toInt() and 0xFF)
        assertEquals(100, rgb[3].toInt() and 0xFF)
    }
}
