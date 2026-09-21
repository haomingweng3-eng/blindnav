package com.blindnav.mobile.risk

import com.blindnav.mobile.feedback.FeedbackPriority
import com.blindnav.mobile.inference.Detection
import com.blindnav.mobile.inference.FrameDetections
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TemporalRiskEngineTest {
    @Test
    fun growingCentralTargetProducesWarningFeedback() {
        val engine = TemporalRiskEngine(loomingThresholdPerSecond = 2f, urgentThresholdPerSecond = 20f)

        assertTrue(engine.update(frame(0, 0, 40f, 40f, 50f, 50f)).isEmpty())
        val alerts = engine.update(frame(100, 1, 35f, 35f, 55f, 55f))

        assertEquals(1, alerts.size)
        assertEquals("bicycle-1", alerts[0].trackId)
        assertEquals("front", alerts[0].direction)
        assertEquals(FeedbackPriority.WARNING, alerts[0].feedback.priority)
    }

    @Test
    fun staticTargetDoesNotProduceAlert() {
        val engine = TemporalRiskEngine(loomingThresholdPerSecond = 2f)

        engine.update(frame(0, 0, 40f, 40f, 50f, 50f))
        assertTrue(engine.update(frame(100, 1, 40f, 40f, 50f, 50f)).isEmpty())
    }

    @Test
    fun lateralTargetOutsideWalkingCorridorIsIgnored() {
        val engine = TemporalRiskEngine(loomingThresholdPerSecond = 2f)

        engine.update(frame(0, 0, 5f, 40f, 15f, 50f))
        assertTrue(engine.update(frame(100, 1, 2f, 40f, 20f, 50f)).isEmpty())
    }

    private fun frame(ts: Long, sourceFrame: Long, left: Float, top: Float, right: Float, bottom: Float) =
        FrameDetections(
            sourceFrame = sourceFrame,
            captureTsMs = ts,
            frameWidth = 100,
            frameHeight = 100,
            detections = listOf(Detection(1, 0.9f, floatArrayOf(left, top, right, bottom))),
        )
}
