package com.blindnav.mobile.inference

import kotlin.math.max

/**
 * Keeps broad two-wheeler detections only when a person overlaps the vehicle.
 * The gate is a conservative false-alert filter for parked scooter rows; it is
 * not a truth labeler and it does not change the detector's box coordinates.
 */
class RiderGateDetector(
    private val twoWheelerDetector: Detector,
    private val personDetector: Detector,
    private val personConfidence: Float = 0.50f,
    private val minOverlap: Float = 0.25f,
    private val personStride: Int = 2,
) : Detector, AutoCloseable {
    init {
        require(personConfidence in 0f..1f)
        require(minOverlap in 0f..1f)
        require(personStride >= 1)
    }

    private var calls = 0
    private var cachedPeople: List<Detection> = emptyList()

    override fun detect(frame: RgbFrame): List<Detection> {
        val candidates = twoWheelerDetector.detect(frame)
            .filter { it.classId == TWO_WHEELER_CLASS_ID }
        if (candidates.isEmpty()) return emptyList()

        if (calls % personStride == 0 || cachedPeople.isEmpty()) {
            cachedPeople = personDetector.detect(frame)
                .filter { it.classId == PERSON_CLASS_ID && it.confidence >= personConfidence }
        }
        calls += 1
        return candidates.filter { candidate ->
            cachedPeople.any { person -> overlapInCandidate(person.box, candidate.box) >= minOverlap }
        }
    }

    override fun close() {
        (twoWheelerDetector as? AutoCloseable)?.close()
        (personDetector as? AutoCloseable)?.close()
    }

    private fun overlapInCandidate(person: FloatArray, candidate: FloatArray): Float {
        if (!validBox(person) || !validBox(candidate)) return 0f
        val left = max(person[0], candidate[0])
        val top = max(person[1], candidate[1])
        val right = minOf(person[2], candidate[2])
        val bottom = minOf(person[3], candidate[3])
        val intersection = max(0f, right - left) * max(0f, bottom - top)
        val candidateArea = (candidate[2] - candidate[0]) * (candidate[3] - candidate[1])
        return if (candidateArea <= 0f) 0f else intersection / candidateArea
    }

    private fun validBox(box: FloatArray): Boolean =
        box.size == 4 && box[2] > box[0] && box[3] > box[1]

    private companion object {
        const val PERSON_CLASS_ID = 0
        const val TWO_WHEELER_CLASS_ID = 1
    }
}
