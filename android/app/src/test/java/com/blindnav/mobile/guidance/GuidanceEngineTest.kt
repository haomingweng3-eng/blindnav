package com.blindnav.mobile.guidance

import com.blindnav.mobile.inference.Detection
import com.blindnav.mobile.inference.FrameDetections
import com.blindnav.mobile.risk.RiskTrackSnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class GuidanceEngineTest {
    @Test
    fun emptyRouteEmitsKeepStraight() {
        val engine = GuidanceEngine()
        val frame = frame(0, emptyList())
        val region = GeometryWalkableRegionEstimator().estimate(frame)
        val decision = engine.update(frame, region, emptyList(), emptyList())
        assertEquals(GuidanceState.KEEP_STRAIGHT, decision.state)
        assertNotNull(decision.feedback)
    }

    @Test
    fun centralBlockerBecomesCautionAfterTwoFrames() {
        val engine = GuidanceEngine()
        val detections = listOf(Detection(1, 0.9f, floatArrayOf(35f, 30f, 65f, 95f)))
        val first = frame(0, detections)
        val region = GeometryWalkableRegionEstimator().estimate(first)
        engine.update(first, region, emptyList(), emptyList())
        val second = frame(1, detections)
        val decision = engine.update(second, region, emptyList(), emptyList())
        assertEquals(GuidanceState.CAUTION, decision.state)
        assertNotNull(decision.feedback)
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

    private fun frame(sourceFrame: Long, detections: List<Detection>) = FrameDetections(
        sourceFrame = sourceFrame,
        captureTsMs = sourceFrame * 100L,
        frameWidth = 100,
        frameHeight = 100,
        detections = detections,
    )
}
