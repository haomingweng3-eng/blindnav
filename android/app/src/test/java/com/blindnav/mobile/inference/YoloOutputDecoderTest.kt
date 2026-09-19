package com.blindnav.mobile.inference

import org.junit.Assert.assertEquals
import org.junit.Test

class YoloOutputDecoderTest {
    @Test
    fun decodesChannelMajorYoloOutputBackToImageCoordinates() {
        val candidates = 3
        val raw = FloatArray(84 * candidates)
        raw[0 * candidates + 0] = 320f
        raw[1 * candidates + 0] = 320f
        raw[2 * candidates + 0] = 100f
        raw[3 * candidates + 0] = 80f
        raw[(4 + 1) * candidates + 0] = 0.9f

        val detections = YoloOutputDecoder.decode(
            raw = raw,
            candidates = candidates,
            originalWidth = 640,
            originalHeight = 640,
            ratio = 1f,
            padLeft = 0f,
            padTop = 0f,
            confidenceThreshold = 0.25f,
        )

        assertEquals(1, detections.size)
        assertEquals(1, detections[0].classId)
        assertEquals(0.9f, detections[0].confidence, 0.001f)
        assertEquals(listOf(270f, 280f, 370f, 360f), detections[0].box.toList())
    }

    @Test
    fun suppressesOverlappingSameClassCandidates() {
        val candidates = 2
        val raw = FloatArray(84 * candidates)
        fun setCandidate(index: Int, cx: Float, score: Float) {
            raw[0 * candidates + index] = cx
            raw[1 * candidates + index] = 320f
            raw[2 * candidates + index] = 100f
            raw[3 * candidates + index] = 80f
            raw[(4 + 0) * candidates + index] = score
        }
        setCandidate(0, 320f, 0.9f)
        setCandidate(1, 325f, 0.8f)

        val detections = YoloOutputDecoder.decode(
            raw, candidates, 640, 640, 1f, 0f, 0f, 0.7f, 0.5f
        )

        assertEquals(1, detections.size)
        assertEquals(0.9f, detections[0].confidence, 0.001f)
    }
}
