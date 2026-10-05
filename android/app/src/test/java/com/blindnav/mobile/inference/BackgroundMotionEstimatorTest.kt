package com.blindnav.mobile.inference

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

class BackgroundMotionEstimatorTest {
    @Test
    fun acceptsDistributedTranslationAndReportsDisplacementInFramePixels() {
        val width = 96
        val height = 64
        val first = textured(width, height)
        val second = shifted(first, width, height, 2, 1)
        val estimator = BackgroundMotionEstimator()

        val initial = estimator.updateRecordedGray(width, height, first, width, height, 0, emptyList())
        val motion = estimator.updateRecordedGray(width, height, second, width, height, 33, emptyList())

        assertFalse(initial.reliable)
        assertTrue(motion.reliable)
        assertTrue(motion.matches >= 8)
        assertTrue(motion.inliers >= 8)
        assertTrue(abs(motion.dxPixels - 2f) <= 0.6f)
        assertTrue(abs(motion.dyPixels - 1f) <= 0.6f)
    }

    @Test
    fun refusesFlatImageInsteadOfInventingCameraMotion() {
        val estimator = BackgroundMotionEstimator()
        val flat = ByteArray(96 * 64) { 128.toByte() }

        estimator.updateRecordedGray(96, 64, flat, 96, 64, 0, emptyList())
        val motion = estimator.updateRecordedGray(96, 64, flat, 96, 64, 33, emptyList())

        assertFalse(motion.reliable)
        assertEquals("insufficient_matches", motion.reason)
    }

    private fun textured(width: Int, height: Int): ByteArray = ByteArray(width * height) { index ->
        val x = index % width
        val y = index / width
        ((x * 37 + y * 61 + ((x * y * 13) % 97) + ((x xor y) * 11)) and 255).toByte()
    }

    private fun shifted(source: ByteArray, width: Int, height: Int, dx: Int, dy: Int): ByteArray =
        ByteArray(source.size) { index ->
            val x = index % width
            val y = index / width
            val sx = (x - dx).coerceIn(0, width - 1)
            val sy = (y - dy).coerceIn(0, height - 1)
            source[sy * width + sx]
        }
}
