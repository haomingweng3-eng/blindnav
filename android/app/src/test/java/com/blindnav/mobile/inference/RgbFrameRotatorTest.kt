package com.blindnav.mobile.inference

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class RgbFrameRotatorTest {
    @Test
    fun rotatesClockwiseAndSwapsDimensions() {
        val source = frame(2, 3, 1, 2, 3, 4, 5, 6)

        val rotated = RgbFrameRotator.rotate(source, 90)

        assertEquals(3, rotated.width)
        assertEquals(2, rotated.height)
        assertArrayEquals(pixels(5, 3, 1, 6, 4, 2), rotated.rgb)
    }

    @Test
    fun supportsHalfTurnAndCounterClockwiseRotation() {
        val source = frame(2, 3, 1, 2, 3, 4, 5, 6)

        assertArrayEquals(pixels(6, 5, 4, 3, 2, 1), RgbFrameRotator.rotate(source, 180).rgb)
        assertArrayEquals(pixels(2, 4, 6, 1, 3, 5), RgbFrameRotator.rotate(source, 270).rgb)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsUnsupportedCameraRotation() {
        RgbFrameRotator.rotate(frame(1, 1, 1), 45)
    }

    private fun frame(width: Int, height: Int, vararg values: Int): RgbFrame =
        RgbFrame(width, height, pixels(*values))

    private fun pixels(vararg values: Int): ByteArray =
        values.flatMap { value -> listOf(value.toByte(), 0, 0) }.toByteArray()
}
