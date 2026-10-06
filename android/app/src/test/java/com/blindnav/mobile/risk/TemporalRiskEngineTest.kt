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
    fun lateralApproachKeepsTargetBearingForFeedback() {
        val engine = TemporalRiskEngine(loomingThresholdPerSecond = 2f, urgentThresholdPerSecond = 20f)

        engine.update(frame(0, 0, 40f, 40f, 50f, 50f))
        val alerts = engine.update(frame(100, 1, 37f, 35f, 57f, 55f))

        assertEquals(1, alerts.size)
        assertEquals("front", alerts[0].direction)
    }

    @Test
    fun boxEdgeTouchingCorridorDoesNotCountWhenContactPointIsOutside() {
        val engine = TemporalRiskEngine(
            loomingThresholdPerSecond = 2f,
            corridorHalfWidth = 0.18f,
        )

        engine.update(frame(0, 0, 65f, 40f, 75f, 50f))
        assertTrue(engine.update(frame(100, 1, 65f, 35f, 80f, 55f)).isEmpty())
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

    @Test
    fun associatesTwoSameClassTargetsIndependently() {
        val engine = TemporalRiskEngine(loomingThresholdPerSecond = 2f, urgentThresholdPerSecond = 20f)
        engine.update(
            frameWithDetections(
                0,
                0,
                detection(40f, 40f, 50f, 50f),
                detection(5f, 40f, 15f, 50f),
            ),
        )

        val alerts = engine.update(
            frameWithDetections(
                100,
                1,
                detection(35f, 35f, 55f, 55f),
                detection(5f, 40f, 15f, 50f),
            ),
        )

        assertEquals(1, alerts.size)
        assertEquals("bicycle-1", alerts[0].trackId)
    }

    @Test
    fun frameGapDoesNotReuseOldGrowthAsAConfirmedApproach() {
        val engine = TemporalRiskEngine(loomingThresholdPerSecond = 2f, urgentThresholdPerSecond = 20f)

        engine.update(frame(0, 0, 40f, 40f, 50f, 50f))
        val alerts = engine.update(frame(100, 3, 35f, 35f, 55f, 55f))

        assertTrue(alerts.isEmpty())
        assertEquals(1, engine.currentTracks.size)
        assertEquals(0, engine.currentTracks.single().riskLevel)
    }

    @Test
    fun reliableBackgroundMotionIsRemovedBeforeApproachDecision() {
        val engine = com.blindnav.mobile.TwoWheelerRuntimeConfig.createRiskEngine()
        val uncompensated = com.blindnav.mobile.TwoWheelerRuntimeConfig.createRiskEngine()

        engine.update(frame(0, 0, 40f, 40f, 50f, 50f))
        uncompensated.update(frame(0, 0, 40f, 40f, 50f, 50f))
        val cameraShift = com.blindnav.mobile.inference.BackgroundMotion(
            fromTimestampMs = 0,
            toTimestampMs = 100,
            dyPixels = 15f,
            reliable = true,
            matches = 12,
            inliers = 10,
            reason = "translation_consensus",
        )
        val alerts = engine.update(
            frameWithDetections(
                100,
                1,
                detection(35f, 45f, 55f, 65f),
                backgroundMotion = cameraShift,
            ),
        )

        assertTrue(alerts.isEmpty())
        assertTrue(uncompensated.update(frame(100, 1, 35f, 45f, 55f, 65f)).isNotEmpty())
        val history = engine.currentTracks.single().roadHistory
        assertEquals(65f, history[0].y, .001f)
        assertEquals(65f, history[1].y, .001f)
    }

    @Test
    fun lowConfidenceDetectionMaintainsButDoesNotCreateTrack() {
        val engine = com.blindnav.mobile.TwoWheelerRuntimeConfig.createRiskEngine()
        val weak = detection(40f, 40f, 50f, 50f).copy(confidence = .15f)
        engine.update(frameWithDetections(0, 0, weak))
        assertTrue(engine.currentTracks.isEmpty())
        engine.update(frame(100, 1, 40f, 40f, 50f, 50f))
        val id = engine.currentTracks.single().trackId
        engine.update(frameWithDetections(200, 2, weak))
        assertEquals(id, engine.currentTracks.single().trackId)
        assertEquals(2, engine.currentTracks.single().roadHistory.size)
    }

    @Test
    fun broadPhoneModelClassesUseTheSameRouteRiskPath() {
        for (classId in listOf(0, 2)) {
            val engine = com.blindnav.mobile.TwoWheelerRuntimeConfig.createRiskEngine()
            engine.update(frameWithDetections(0, 0, detection(40f, 40f, 50f, 50f, classId)))
            val alerts = engine.update(
                frameWithDetections(100, 1, detection(35f, 35f, 55f, 55f, classId)),
            )

            assertEquals(1, alerts.size)
            assertEquals(
                classId,
                when (engine.currentTracks.single().className) {
                    "行人" -> 0
                    "三轮车" -> 2
                    "四轮车" -> 3
                    else -> -1
                },
            )
        }
        val parkedFourWheeler = com.blindnav.mobile.TwoWheelerRuntimeConfig.createRiskEngine()
        parkedFourWheeler.update(frameWithDetections(0, 0, detection(40f, 40f, 50f, 50f, 3)))
        assertTrue(parkedFourWheeler.update(frameWithDetections(100, 1, detection(39f, 40f, 51f, 50f, 3))).isEmpty())
    }

    @Test
    fun parkedFourWheelerCanWarnAsObstacleButNeverBecomesDanger() {
        val engine = com.blindnav.mobile.TwoWheelerRuntimeConfig.createRiskEngine()
        engine.update(frameWithDetections(0, 0, detection(30f, 20f, 70f, 80f, classId = 3)))
        val first = engine.update(frameWithDetections(100, 1, detection(29f, 20f, 71f, 80f, classId = 3)))
        assertTrue(first.all { it.feedback.priority != FeedbackPriority.URGENT })
        assertTrue(engine.currentTracks.single().riskLevel <= 1)
        engine.update(frameWithDetections(200, 2, detection(30f, 20f, 70f, 80f, classId = 3)))
        assertTrue(engine.currentTracks.single().riskLevel <= 1)
    }

    @Test
    fun confirmedDangerDoesNotFlickerBackToSafeOnOneFlatFrame() {
        val engine = TemporalRiskEngine(
            loomingThresholdPerSecond = 0.1f,
            urgentThresholdPerSecond = 0.2f,
            minObservations = 2,
            earlyUrgentTimeToCloseSeconds = 1f,
        )

        engine.update(frame(0, 0, 40f, 40f, 50f, 50f))
        val firstDanger = engine.update(frame(100, 1, 35f, 35f, 55f, 55f))
        assertTrue(firstDanger.isNotEmpty())
        assertEquals(2, engine.currentTracks.single().riskLevel)

        engine.update(frame(200, 2, 35f, 35f, 55f, 55f))
        assertEquals(2, engine.currentTracks.single().riskLevel)
    }

    @Test
    fun confirmedWarningDoesNotDropToSafeOnOneFlatFrame() {
        val engine = TemporalRiskEngine(
            loomingThresholdPerSecond = 2f,
            urgentThresholdPerSecond = 20f,
            minObservations = 2,
        )

        engine.update(frame(0, 0, 40f, 40f, 50f, 50f))
        val warning = engine.update(frame(100, 1, 35f, 35f, 55f, 55f))
        assertTrue(warning.isNotEmpty())
        assertEquals(1, engine.currentTracks.single().riskLevel)

        engine.update(frame(200, 2, 35f, 35f, 55f, 55f))
        assertEquals(1, engine.currentTracks.single().riskLevel)
    }

    @Test
    fun unreliableBackgroundDoesNotInventLateralEntry() {
        val engine = com.blindnav.mobile.TwoWheelerRuntimeConfig.createRiskEngine()
        val unavailable = com.blindnav.mobile.inference.BackgroundMotion(0, 100, reason = "insufficient_matches")
        engine.update(frame(0, 0, 10f, 40f, 20f, 60f))
        assertTrue(engine.update(frameWithDetections(100, 1, detection(20f, 40f, 30f, 60f),
            backgroundMotion = unavailable)).isEmpty())
        assertTrue(engine.update(frameWithDetections(200, 2, detection(25f, 40f, 35f, 60f),
            backgroundMotion = unavailable.copy(fromTimestampMs = 100, toTimestampMs = 200))).isEmpty())
    }

    @Test
    fun closeCentralTargetDoesNotRemainGreenWhenMotionIsUnavailable() {
        val engine = com.blindnav.mobile.TwoWheelerRuntimeConfig.createRiskEngine()
        val unavailable = com.blindnav.mobile.inference.BackgroundMotion(
            fromTimestampMs = 0,
            toTimestampMs = 100,
            reason = "insufficient_matches",
        )
        engine.update(frame(0, 0, 30f, 20f, 70f, 80f))
        val alerts = engine.update(
            frameWithDetections(
                100,
                1,
                detection(30f, 20f, 70f, 80f),
                backgroundMotion = unavailable,
            ),
        )
        assertEquals(1, alerts.size)
        assertEquals(FeedbackPriority.WARNING, alerts.single().feedback.priority)
        assertEquals(1, engine.currentTracks.single().riskLevel)
    }

    private fun frame(ts: Long, sourceFrame: Long, left: Float, top: Float, right: Float, bottom: Float) =
        frameWithDetections(ts, sourceFrame, detection(left, top, right, bottom))

    private fun frameWithDetections(
        ts: Long,
        sourceFrame: Long,
        vararg detections: Detection,
        backgroundMotion: com.blindnav.mobile.inference.BackgroundMotion? = null,
    ) =
        FrameDetections(
            sourceFrame = sourceFrame,
            captureTsMs = ts,
            frameWidth = 100,
            frameHeight = 100,
            backgroundMotion = backgroundMotion,
            detections = detections.toList(),
        )

    private fun detection(left: Float, top: Float, right: Float, bottom: Float, classId: Int = 1) =
        Detection(classId, 0.9f, floatArrayOf(left, top, right, bottom))
}
