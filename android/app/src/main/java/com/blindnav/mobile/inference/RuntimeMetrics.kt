package com.blindnav.mobile.inference

import kotlin.math.ceil

data class RuntimeMetricsSnapshot(
    val processedFrames: Int,
    val averageProcessingMs: Double,
    val p95ProcessingMs: Long,
    val droppedFrames: Int,
    val fps: Double,
)

/** Small, bounded runtime summary for the on-device acceptance screen. */
class RuntimeMetrics(
    private val clockMs: () -> Long = { System.currentTimeMillis() },
    private val maxSamples: Int = 120,
) {
    private val processingSamples = ArrayDeque<Long>()
    private var startedAtMs: Long? = null
    private var processedFrames = 0
    private var droppedFrames = 0

    init {
        require(maxSamples > 0) { "maxSamples must be positive" }
    }

    fun record(processingMs: Long, droppedSinceLast: Int) {
        require(processingMs >= 0) { "processingMs must be non-negative" }
        require(droppedSinceLast >= 0) { "droppedSinceLast must be non-negative" }
        if (startedAtMs == null) startedAtMs = clockMs()
        processedFrames += 1
        droppedFrames += droppedSinceLast
        processingSamples.addLast(processingMs)
        while (processingSamples.size > maxSamples) processingSamples.removeFirst()
    }

    fun snapshot(): RuntimeMetricsSnapshot {
        val samples = processingSamples.toList().sorted()
        val average = if (samples.isEmpty()) 0.0 else samples.average()
        val p95 = if (samples.isEmpty()) 0L else {
            val index = (ceil(samples.size * 0.95).toInt() - 1).coerceIn(0, samples.lastIndex)
            samples[index]
        }
        val elapsedMs = startedAtMs?.let { (clockMs() - it).coerceAtLeast(1L) } ?: 0L
        val fps = if (elapsedMs == 0L) 0.0 else processedFrames * 1000.0 / elapsedMs
        return RuntimeMetricsSnapshot(processedFrames, average, p95, droppedFrames, fps)
    }

    fun reset() {
        processingSamples.clear()
        startedAtMs = null
        processedFrames = 0
        droppedFrames = 0
    }
}
