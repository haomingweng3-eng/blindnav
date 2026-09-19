package com.blindnav.mobile.inference

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LetterboxPreprocessorTest {
    @Test
    fun keepsAspectRatioAndUsesGrayPadding() {
        // Two RGB pixels: red, then blue.
        val rgb = byteArrayOf(
            255.toByte(), 0, 0,
            0, 0, 255.toByte(),
        )

        val result = LetterboxPreprocessor(targetSize = 4).convert(rgb, 2, 1)

        assertEquals(4 * 4 * 3, result.chw.size)
        assertEquals(4, result.scaledWidth)
        assertEquals(2, result.scaledHeight)
        assertEquals(0, result.padLeft)
        assertEquals(1, result.padTop)
        assertEquals(0.5f, result.chw[result.rgbIndex(0, 0, 0)], 0.01f)
        assertEquals(1.0f, result.chw[result.rgbIndex(1, 1, 0)], 0.01f)
        assertEquals(1.0f, result.chw[result.rgbIndex(2, 1, 2)], 0.01f)
    }

    @Test
    fun rejectsWrongRgbBufferSize() {
        val error = runCatching {
            LetterboxPreprocessor(4).convert(byteArrayOf(1, 2), 2, 1)
        }.exceptionOrNull()

        assertTrue(error is IllegalArgumentException)
    }
}
