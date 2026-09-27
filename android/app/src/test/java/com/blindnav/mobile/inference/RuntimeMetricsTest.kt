package com.blindnav.mobile.inference

import org.junit.Assert.assertEquals
import org.junit.Test

class RuntimeMetricsTest {
    @Test
    fun calculatesFpsAverageP95AndDroppedFrames() {
        var now = 1_000L
        val metrics = RuntimeMetrics(clockMs = { now })

        metrics.record(processingMs = 10L, droppedSinceLast = 1)
        now = 1_100L
        metrics.record(processingMs = 20L, droppedSinceLast = 2)
        now = 1_200L
        metrics.record(processingMs = 30L, droppedSinceLast = 0)

        val snapshot = metrics.snapshot()
        assertEquals(3, snapshot.processedFrames)
        assertEquals(20.0, snapshot.averageProcessingMs, 0.001)
        assertEquals(30L, snapshot.p95ProcessingMs)
        assertEquals(3, snapshot.droppedFrames)
        assertEquals(15.0, snapshot.fps, 0.001)
    }

    @Test
    fun resetClearsPreviousRun() {
        var now = 500L
        val metrics = RuntimeMetrics(clockMs = { now })
        metrics.record(processingMs = 8L, droppedSinceLast = 4)
        metrics.reset()

        now = 1_500L
        val snapshot = metrics.snapshot()
        assertEquals(0, snapshot.processedFrames)
        assertEquals(0, snapshot.droppedFrames)
        assertEquals(0.0, snapshot.fps, 0.001)
    }
}
