package com.blindnav.mobile.guidance

import com.blindnav.mobile.inference.Detection
import com.blindnav.mobile.inference.FrameDetections
import com.blindnav.mobile.inference.BackgroundMotion
import com.blindnav.mobile.risk.RiskTrackSnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class GuidanceEngineTest {
    @Test
    fun emptyDetectionsDoNotProveWalkableGround() {
        val engine = GuidanceEngine()
        val frame = frame(0, emptyList())
        val region = GeometryWalkableRegionEstimator().estimate(frame)
        val decision = engine.update(frame, region, emptyList(), emptyList())
        assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN, decision.state)
        assertNotNull(decision.feedback)
    }

    @Test
    fun centralBlockerBecomesCautionAfterTwoFrames() {
        val engine = GuidanceEngine()
        val detections = listOf(Detection(1, 0.9f, floatArrayOf(35f, 30f, 65f, 95f)))
        val first = frame(0, detections)
        val region = GeometryWalkableRegionEstimator().estimate(first)
        assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN, engine.update(first, region, emptyList(), emptyList()).state)
        val second = frame(1, detections)
        val decision = engine.update(second, region, emptyList(), emptyList())
        assertEquals(GuidanceState.CAUTION, decision.state)
        assertNotNull(decision.feedback)
    }

    @Test
    fun asymmetricBoxWithoutGroundEvidenceDoesNotGuessDirection() {
        val engine = GuidanceEngine()
        val detections = listOf(Detection(1, 0.9f, floatArrayOf(45f, 30f, 70f, 95f)))
        val first = frame(0, detections)
        val region = GeometryWalkableRegionEstimator().estimate(first)
        assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN, engine.update(first, region, emptyList(), emptyList()).state)
        val second = frame(1, detections)
        assertEquals(GuidanceState.CAUTION, engine.update(second, region, emptyList(), emptyList()).state)
    }

    @Test
    fun semanticSideEvidenceRequiresMotionAndThreeConsistentFrames() {
        val engine = GuidanceEngine()
        val detections = listOf(Detection(1, 0.9f, floatArrayOf(45f, 30f, 70f, 95f)))
        val region = evidence(left = 0.96f, right = 0.30f)
        assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN, engine.update(frame(0, detections), region, emptyList(), emptyList()).state)
        assertEquals(GuidanceState.CAUTION, engine.update(reliableFrame(1, detections), region, emptyList(), emptyList()).state)
        assertEquals(GuidanceState.CAUTION, engine.update(reliableFrame(2, detections), region, emptyList(), emptyList()).state)
        assertEquals(GuidanceState.MOVE_LEFT, engine.update(reliableFrame(3, detections), region, emptyList(), emptyList()).state)
        assertEquals(GuidanceState.CAUTION, engine.update(frame(4, detections), region, emptyList(), emptyList()).state)
    }

    @Test
    fun verifiedForwardSurfaceAllowsStraightAfterThreeFrames() {
        val engine = GuidanceEngine()
        val region = evidence(forward = 0.96f)
        for (i in 0L..1L) assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN,
            engine.update(reliableFrame(i, emptyList()), region, emptyList(), emptyList()).state)
        assertEquals(GuidanceState.KEEP_STRAIGHT,
            engine.update(reliableFrame(2, emptyList()), region, emptyList(), emptyList()).state)
    }

    @Test
    fun staleMotionAndLargeFrameGapResetDirectionConfirmation() {
        val engine = GuidanceEngine()
        val region = evidence(forward = 0.96f)
        for (i in 0L..2L) engine.update(reliableFrame(i, emptyList()), region, emptyList(), emptyList())
        val stale = reliableFrame(3, emptyList()).copy(backgroundMotion = BackgroundMotion(100, 200, reliable = true))
        assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN, engine.update(stale, region, emptyList(), emptyList()).state)
        val delayed = reliableFrame(4, emptyList()).copy(captureTsMs = 2000,
            backgroundMotion = BackgroundMotion(300, 2000, reliable = true))
        assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN, engine.update(delayed, region, emptyList(), emptyList()).state)
    }

    @Test
    fun bothUnprovenSidesCannotAuthorizeDetour() {
        val region = evidence(left = 0.65f, right = 0.65f)
        assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN, region.supportedDirection())
        assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN, region.copy(source = "geometry_fallback", leftSupport = 1f).supportedDirection())
    }

    private fun evidence(forward: Float = 0f, left: Float = 0f, right: Float = 0f) = WalkableRegion(
        0.36f, 0.64f, 0.48f, 0.9f, "segformer_ade20k", surface = "road",
        forwardSupport = forward, leftSupport = left, rightSupport = right,
    )

    private fun reliableFrame(sourceFrame: Long, detections: List<Detection>) = frame(sourceFrame, detections).let {
        it.copy(backgroundMotion = BackgroundMotion(it.captureTsMs - 100, it.captureTsMs, reliable = true))
    }

    @Test
    fun urgentRiskUsesDangerState() {
        val engine = GuidanceEngine()
        val frame = frame(0, emptyList())
        val region = GeometryWalkableRegionEstimator().estimate(frame)
        val track = RiskTrackSnapshot(
            trackId = "two-wheeler-1",
            box = floatArrayOf(35f, 20f, 65f, 95f),
            roadHistory = emptyList(),
            riskLevel = 2,
        )
        val decision = engine.update(frame, region, listOf(track), emptyList())
        assertEquals(GuidanceState.DANGER, decision.state)
        assertNotNull(decision.feedback)
    }

    @Test
    fun unavailableCameraMotionUsesSlowDownState() {
        val engine = GuidanceEngine()
        val frame = frame(0, emptyList()).copy(
            backgroundMotion = BackgroundMotion(
                fromTimestampMs = 0L,
                toTimestampMs = 0L,
                reliable = false,
                reason = "initial",
            ),
        )
        val region = GeometryWalkableRegionEstimator().estimate(frame)
        val decision = engine.update(frame, region, emptyList(), emptyList())
        assertEquals(GuidanceState.UNKNOWN_SLOW_DOWN, decision.state)
    }

    @Test
    fun warningFeedbackHasCooldownAcrossStateFlap() {
        val engine = GuidanceEngine(repeatMs = 2_500L)
        val detections = listOf(Detection(1, 0.9f, floatArrayOf(35f, 30f, 65f, 95f)))
        val first = frame(0, detections)
        val region = GeometryWalkableRegionEstimator().estimate(first)
        engine.update(first, region, emptyList(), emptyList())
        val second = frame(1, detections)
        val decision = engine.update(second, region, emptyList(), emptyList())
        assertNotNull(decision.feedback)
        val repeated = engine.update(second, region, emptyList(), emptyList())
        assertEquals(null, repeated.feedback)
    }

    private fun frame(sourceFrame: Long, detections: List<Detection>) = FrameDetections(
        sourceFrame = sourceFrame,
        captureTsMs = sourceFrame * 100L,
        frameWidth = 100,
        frameHeight = 100,
        detections = detections,
    )
}
