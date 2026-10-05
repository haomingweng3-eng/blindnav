package com.blindnav.mobile.risk

import com.blindnav.mobile.feedback.FeedbackAction
import com.blindnav.mobile.feedback.FeedbackPriority
import com.blindnav.mobile.inference.Detection
import com.blindnav.mobile.inference.FrameDetections
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.max

data class AndroidRiskAlert(
    val trackId: String,
    val className: String,
    val direction: String,
    val loomingPerSecond: Float,
    val feedback: FeedbackAction,
)

data class RoadObservation(val x: Float, val y: Float, val timestampMs: Long)

/** Current observations only; a lost target is not drawn as a fresh detection. */
data class RiskTrackSnapshot(
    val trackId: String,
    val box: FloatArray,
    val roadHistory: List<RoadObservation>,
    val riskLevel: Int,
    val className: String = "目标",
)

/**
 * Conservative Android MVP risk adapter for the live camera path.
 *
 * This is intentionally not presented as ByteTrack or a calibrated collision
 * predictor. It keeps lightweight temporal states for multiple targets of each
 * supported COCO class, requires a central target and a positive area-growth
 * trend, and emits feedback only after consecutive frames. The Python risk
 * engine remains the experiment reference until Android-side thresholds are
 * calibrated on real footage.
 */
class TemporalRiskEngine(
    private val loomingThresholdPerSecond: Float = 2f,
    private val urgentThresholdPerSecond: Float = 5f,
    private val maxCenterJumpFraction: Float = 0.35f,
    private val cooldownMs: Long = 1_000L,
    private val twoWheelerMode: Boolean = false,
    private val minConfidence: Float = MIN_CONFIDENCE,
    // ByteTrack-style split: low-confidence detections may maintain an
    // existing track but may not create a new target.
    private val minNewTrackConfidence: Float = minConfidence,
    private val minObservations: Int = 2,
    private val minApproachArea: Float = 0f,
    private val approachVerticalThresholdPerSecond: Float = 0f,
    private val corridorHalfWidth: Float = 0.30f,
    private val minRoadContactY: Float = 0f,
    private val routeBlockedWarning: Boolean = false,
    // Keep the generic engine conservative; the live two-wheeler app opts in
    // to the earlier 1.2 s escalation through MainActivity.
    private val earlyUrgentTimeToCloseSeconds: Float = 0f,
) {
    init {
        require(loomingThresholdPerSecond >= 0f)
        require(urgentThresholdPerSecond >= loomingThresholdPerSecond)
        require(maxCenterJumpFraction > 0f)
        require(minObservations >= 2)
        require(minApproachArea >= 0f)
        require(minNewTrackConfidence >= minConfidence)
        require(approachVerticalThresholdPerSecond >= 0f)
        require(corridorHalfWidth > 0f && corridorHalfWidth <= 0.5f)
        require(minRoadContactY in 0f..1f)
        require(earlyUrgentTimeToCloseSeconds >= 0f)
    }

    private data class Observation(
        val box: FloatArray,
        val centerX: Float,
        val centerY: Float,
        val bottom: Float,
        val areaFraction: Float,
        val timestampMs: Long,
        val cameraX: Float,
        val cameraY: Float,
        val motionReliable: Boolean,
    )

    private data class State(
        val trackId: String,
        val box: FloatArray,
        val centerX: Float,
        val centerY: Float,
        val areaFraction: Float,
        val timestampMs: Long,
        val sourceFrame: Long,
        val observations: Int,
        val lastAlertMs: Long,
        val lastAlertLevel: Int,
        val riskLevel: Int,
        val history: List<Observation>,
    )

    private val states = mutableMapOf<Int, MutableList<State>>()
    private val nextTrackNumber = mutableMapOf<Int, Int>()
    private var lastTimestampMs: Long? = null
    private var lastSourceFrame: Long? = null
    private var dimensions: Pair<Int, Int>? = null
    private var cameraX = 0f
    private var cameraY = 0f
    var currentTracks: List<RiskTrackSnapshot> = emptyList()
        private set

    fun update(frame: FrameDetections): List<AndroidRiskAlert> {
        require(frame.frameWidth > 0 && frame.frameHeight > 0)
        if (lastTimestampMs?.let { frame.captureTsMs <= it } == true ||
            lastSourceFrame?.let { frame.sourceFrame <= it } == true ||
            (dimensions != null && dimensions != (frame.frameWidth to frame.frameHeight))
        ) reset()
        val motion = frame.backgroundMotion
        val motionReliable = motion == null || (motion.reliable && motion.fromTimestampMs == lastTimestampMs &&
            motion.toTimestampMs == frame.captureTsMs && motion.dxPixels.isFinite() && motion.dyPixels.isFinite())
        if (motion != null && motionReliable) {
            cameraX += motion.dxPixels
            cameraY += motion.dyPixels
        }
        lastTimestampMs = frame.captureTsMs
        lastSourceFrame = frame.sourceFrame
        dimensions = frame.frameWidth to frame.frameHeight
        val output = mutableListOf<AndroidRiskAlert>()
        val imageArea = frame.frameWidth.toFloat() * frame.frameHeight.toFloat()
        val seenTrackIds = mutableSetOf<String>()

        val acceptedBoxes = mutableListOf<Detection>()
        for (detection in frame.detections.sortedByDescending { it.confidence }) {
            val className = classNames[detection.classId] ?: continue
            if (!detection.confidence.isFinite() || detection.confidence < minConfidence || !validBox(detection.box)) continue
            if (acceptedBoxes.any { it.classId == detection.classId && iou(it.box, detection.box) >= 0.85f }) continue
            acceptedBoxes += detection
            val classId = detection.classId

            val box = detection.box
            val centerX = (box[0] + box[2]) / 2f
            val centerY = (box[1] + box[3]) / 2f
            val areaFraction = ((box[2] - box[0]) * (box[3] - box[1])) / imageArea
            val observation = Observation(box.copyOf(), centerX, centerY, box[3], areaFraction, frame.captureTsMs,
                cameraX, cameraY, motionReliable)
            val classStates = states.getOrPut(classId) { mutableListOf() }
            val previous = classStates
                .filter { it.trackId !in seenTrackIds && frame.captureTsMs - it.timestampMs in 0..STALE_TRACK_MS }
                .mapNotNull { state ->
                    val lastPair = state.history.takeLast(2)
                    val elapsed = (frame.captureTsMs - state.timestampMs).coerceAtMost(500L)
                    val dt = if (lastPair.size == 2) lastPair[1].timestampMs - lastPair[0].timestampMs else 0L
                    val last = state.history.last()
                    val vx = if (dt > 0 && last.motionReliable) (lastPair[1].centerX - lastPair[1].cameraX -
                        lastPair[0].centerX + lastPair[0].cameraX) * elapsed / dt else 0f
                    val vy = if (dt > 0 && last.motionReliable) (lastPair[1].centerY - lastPair[1].cameraY -
                        lastPair[0].centerY + lastPair[0].cameraY) * elapsed / dt else 0f
                    val predictedX = state.centerX + cameraX - last.cameraX + vx
                    val predictedY = state.centerY + cameraY - last.cameraY + vy
                    val distance = distanceFraction(
                        predictedX,
                        predictedY,
                        centerX,
                        centerY,
                        frame.frameWidth,
                        frame.frameHeight,
                    )
                    if (distance > maxCenterJumpFraction) return@mapNotNull null
                    val overlap = iou(floatArrayOf(state.box[0] + cameraX - last.cameraX,
                        state.box[1] + cameraY - last.cameraY, state.box[2] + cameraX - last.cameraX,
                        state.box[3] + cameraY - last.cameraY), box)
                    // Disjoint distant detections must not inherit another
                    // vehicle's motion history or alert cooldown.
                    if (overlap == 0f && distance > 0.12f) return@mapNotNull null
                    val areaRatio = areaFraction / state.areaFraction
                    if (areaRatio !in 0.15f..6f) return@mapNotNull null
                    val normalizedDistance = (distance / maxCenterJumpFraction).coerceIn(0f, 1f)
                    // Prefer spatial overlap, while retaining center-distance
                    // matching for small or briefly occluded targets.
                    state to (overlap * 0.65f + (1f - normalizedDistance) * 0.35f)
                }
                .maxByOrNull { it.second }
                ?.first
            if (previous == null && detection.confidence < minNewTrackConfidence) continue
            val trackId = previous?.trackId ?: newTrackId(classId)
            seenTrackIds += trackId
            val consecutive = previous != null && previous.sourceFrame == frame.sourceFrame - 1 &&
                frame.captureTsMs - previous.timestampMs in 1..MAX_OBSERVATION_GAP_MS
            val next = State(
                trackId = trackId,
                box = box.copyOf(),
                centerX = centerX,
                centerY = centerY,
                areaFraction = areaFraction,
                timestampMs = frame.captureTsMs,
                sourceFrame = frame.sourceFrame,
                observations = if (consecutive) previous!!.observations + 1 else 1,
                lastAlertMs = previous?.lastAlertMs ?: Long.MIN_VALUE,
                lastAlertLevel = previous?.lastAlertLevel ?: 0,
                riskLevel = 0,
                history = ((if (consecutive) previous!!.history else emptyList()) + observation).takeLast(HISTORY_SIZE),
            )
            if (previous != null) classStates.remove(previous)
            classStates += next

            if (previous == null || previous.timestampMs >= frame.captureTsMs) continue
            if (next.observations < minObservations) continue
            val centerJump = distanceFraction(previous.centerX, previous.centerY, centerX, centerY, frame.frameWidth, frame.frameHeight)
            if (centerJump > maxCenterJumpFraction) continue
            val currentX = centerX / frame.frameWidth
            val contactY = next.history.last().bottom / frame.frameHeight
            val corridor = (0.5f - corridorHalfWidth)..(0.5f + corridorHalfWidth)

            val pairs = next.history.takeLast(GROWTH_WINDOW).zipWithNext()
            val growthRates = pairs.mapNotNull { (old, new) ->
                val dtSeconds = (new.timestampMs - old.timestampMs) / 1_000f
                if (dtSeconds <= 0f || old.areaFraction <= 0f || new.areaFraction <= 0f) {
                    null
                } else {
                    ln(new.areaFraction / old.areaFraction) / dtSeconds
                }
            }
            val verticalRates = pairs.mapNotNull { (old, new) ->
                val dtSeconds = (new.timestampMs - old.timestampMs) / 1_000f
                if (dtSeconds <= 0f) null else (new.centerY - old.centerY - new.cameraY + old.cameraY) / frame.frameHeight / dtSeconds
            }
            val bottomRates = pairs.mapNotNull { (old, new) ->
                val dtSeconds = (new.timestampMs - old.timestampMs) / 1_000f
                if (dtSeconds <= 0f) null else (new.bottom - old.bottom - new.cameraY + old.cameraY) / frame.frameHeight / dtSeconds
            }
            val lateralRates = pairs.mapNotNull { (old, new) ->
                val dtSeconds = (new.timestampMs - old.timestampMs) / 1_000f
                if (dtSeconds <= 0f || !new.motionReliable) null else
                    (new.centerX - old.centerX - new.cameraX + old.cameraX) / frame.frameWidth / dtSeconds
            }
            val requiredGrowthSamples = minOf(MIN_GROWTH_SAMPLES, minObservations - 1)
            if (growthRates.size < requiredGrowthSamples) continue
            val looming = median(growthRates)
            val vertical = median(verticalRates)
            val bottomVelocity = median(bottomRates)
            val lateralVelocity = median(lateralRates)
            val futureX = currentX + lateralVelocity * PREDICTION_HORIZON_SECONDS
            // The box edge can touch the corridor while the vehicle itself
            // remains in a parking row. Use the road contact point instead.
            val currentInside = contactY >= minRoadContactY && currentX in corridor
            // Test the whole projected segment, since a crossing vehicle may
            // have already passed the corridor at the horizon endpoint.
            val crossesCorridor = minOf(currentX, futureX) <= corridor.endInclusive &&
                maxOf(currentX, futureX) >= corridor.start
            val insideStreak = next.history.asReversed().takeWhile {
                (it.centerX / frame.frameWidth) in corridor
            }.size
            val enteredFromOutside = next.history.dropLast(1).any {
                it.box[0] / frame.frameWidth > corridor.endInclusive ||
                    it.box[2] / frame.frameWidth < corridor.start
            }
            val predictedEntry = !currentInside && crossesCorridor &&
                abs(lateralVelocity) >= LATERAL_ENTRY_THRESHOLD_PER_SECOND &&
                motionReliable &&
                contactY >= minRoadContactY
            // A lateral crossing needs one extra observation so one detector
            // jitter cannot turn a parked edge target into an alert.
            if (predictedEntry && next.observations < 3) continue
            val exiting = currentInside && futureX !in corridor &&
                abs(lateralVelocity) >= LATERAL_EXIT_THRESHOLD_PER_SECOND
            val insideConfirmed = currentInside && insideStreak >= ROUTE_CONFIRM_FRAMES &&
                (!enteredFromOutside || insideStreak >= ROUTE_CONFIRM_FRAMES)
            val approachPathConflict = if (strictRouteMode) {
                !exiting && (insideConfirmed || predictedEntry)
            } else {
                currentInside
            }
            if (!approachPathConflict) continue
            // Keep a confirmed danger state stable while the same continuous
            // target remains close in the route. Detector jitter or one frame
            // without reliable motion must not make a near collision look
            // safe again. The state is released when the target leaves the
            // corridor, the track is lost, or it shrinks below this hold
            // floor.
            val dangerHold = previous?.riskLevel == 2 &&
                currentInside &&
                insideConfirmed &&
                areaFraction >= DANGER_HOLD_AREA_FRACTION
            if (dangerHold) {
                classStates.remove(next)
                classStates += next.copy(riskLevel = 2)
                continue
            }
            // A bottom edge moving down is the useful near-camera cue. A
            // positive center velocity alone is too easy to trigger from a
            // parked target's jitter when its box is shrinking.
            val positiveApproachMotion = approachVerticalThresholdPerSecond <= 0f ||
                bottomVelocity >= approachVerticalThresholdPerSecond
            val approachMotion = positiveApproachMotion &&
                looming >= -MAX_SHRINK_RATE_FOR_APPROACH
            // Once a continuous target has earned a warning, a short flat or
            // noisy growth sample must not make the same route threat look
            // safe again. Release the hold when the target leaves the
            // corridor, becomes too small, or supplies fresh approach motion
            // that should continue through the normal escalation path.
            val warningHold = previous?.riskLevel == 1 &&
                currentInside &&
                insideConfirmed &&
                areaFraction >= WARNING_HOLD_AREA_FRACTION &&
                !approachMotion
            if (warningHold) {
                val evaluated = next.copy(riskLevel = 1)
                classStates.remove(next)
                classStates += evaluated
                continue
            }
            // A close target in the confirmed route must never remain green
            // merely because camera compensation or a growth sample is
            // unavailable. Escalate conservatively to a warning; only the
            // normal temporal path may promote it to danger.
            val closeRouteWithoutReliableMotion = currentInside &&
                insideStreak >= ROUTE_CONFIRM_FRAMES &&
                areaFraction >= CLOSE_ROUTE_AREA_FRACTION &&
                !motionReliable
            if (closeRouteWithoutReliableMotion) {
                val evaluated = next.copy(riskLevel = 1)
                classStates.remove(next)
                classStates += evaluated
                if (previous.lastAlertMs != Long.MIN_VALUE &&
                    frame.captureTsMs - previous.lastAlertMs < cooldownMs &&
                    previous.lastAlertLevel >= 1
                ) continue
                val direction = directionFor(currentX)
                val feedback = FeedbackAction.fromContract(
                    priority = FeedbackPriority.WARNING.contractName,
                    vibrationMs = listOf(120, 70, 120),
                    tone = "warning",
                    speech = "注意，${directionName(direction)}${className}距离较近，请谨慎",
                    speechDelayMs = 0,
                ) ?: continue
                classStates.remove(evaluated)
                classStates += evaluated.copy(lastAlertMs = frame.captureTsMs, lastAlertLevel = 1)
                output += AndroidRiskAlert(trackId, className, direction, looming, feedback)
                continue
            }
            if (areaFraction < minApproachArea) continue
            val potentialCollisionMotion = approachMotion ||
                looming >= loomingThresholdPerSecond || predictedEntry
            val routeBlocked = routeBlockedWarning && currentInside && insideConfirmed &&
                insideStreak >= ROUTE_CONFIRM_FRAMES && approachMotion && potentialCollisionMotion
            if (!routeBlocked && !predictedEntry && !approachMotion) continue
            if (!routeBlocked && !predictedEntry && looming < loomingThresholdPerSecond) continue

            val predictedAreaFraction = areaFraction * exp(max(looming, 0f) * PREDICTION_HORIZON_SECONDS)
            val timeToCloseSeconds = when {
                areaFraction >= URGENT_AREA_FRACTION -> 0f
                looming > 0f && areaFraction > 0f ->
                    (ln(URGENT_AREA_FRACTION / areaFraction) / looming).coerceAtLeast(0f)
                else -> null
            }
            val predictedClose = predictedAreaFraction >= EARLY_URGENT_AREA_FRACTION ||
                (timeToCloseSeconds != null &&
                    timeToCloseSeconds <= earlyUrgentTimeToCloseSeconds)
            val urgentMotion = approachMotion && (
                looming >= urgentThresholdPerSecond ||
                    (earlyUrgentTimeToCloseSeconds > 0f &&
                        looming >= loomingThresholdPerSecond && predictedClose)
                )
            val priority = if (insideConfirmed && urgentMotion &&
                (areaFraction >= URGENT_AREA_FRACTION || predictedClose)
            ) FeedbackPriority.URGENT else FeedbackPriority.WARNING
            val level = if (priority == FeedbackPriority.URGENT) 2 else 1
            classStates.remove(next)
            val evaluated = next.copy(riskLevel = level)
            classStates += evaluated
            // Escalation is immediate even inside the warning cooldown.
            if (previous.lastAlertMs != Long.MIN_VALUE &&
                frame.captureTsMs - previous.lastAlertMs < cooldownMs &&
                level <= previous.lastAlertLevel
            ) continue
            // Spoken left/right is the target's current bearing. Its travel
            // direction must not tell a blind user the object is on the wrong side.
            val direction = directionFor(currentX)
            val feedback = FeedbackAction.fromContract(
                priority = priority.contractName,
                vibrationMs = if (priority == FeedbackPriority.URGENT) listOf(260, 80, 260) else listOf(120, 70, 120),
                tone = if (priority == FeedbackPriority.URGENT) "danger" else "warning",
                speech = if (priority == FeedbackPriority.URGENT) "危险，${directionName(direction)}${className}快速接近" else "注意，${directionName(direction)}$className",
                speechDelayMs = 0,
            ) ?: continue
            classStates.remove(evaluated)
            classStates += evaluated.copy(lastAlertMs = frame.captureTsMs, lastAlertLevel = level)
            output += AndroidRiskAlert(trackId, className, direction, looming, feedback)
        }
        states.values.forEach { tracks -> tracks.removeAll { frame.captureTsMs - it.timestampMs > STALE_TRACK_MS } }
        currentTracks = states.values.flatten().filter { it.sourceFrame == frame.sourceFrame }.map { state ->
            RiskTrackSnapshot(state.trackId, state.box.copyOf(), state.history.map {
                // Align earlier observed contact points with the current
                // background. This is a stabilized history, never a future path.
                RoadObservation(it.centerX + cameraX - it.cameraX, it.bottom + cameraY - it.cameraY, it.timestampMs)
            }, state.riskLevel, classNames[state.trackId.substringBeforeLast('-').let { key ->
                classKeys.entries.firstOrNull { it.value == key }?.key ?: -1
            }] ?: "目标")
        }
        return output
    }

    fun reset() {
        states.clear()
        nextTrackNumber.clear()
        currentTracks = emptyList()
        lastTimestampMs = null
        lastSourceFrame = null
        dimensions = null
        cameraX = 0f
        cameraY = 0f
    }

    private fun newTrackId(classId: Int): String {
        val number = (nextTrackNumber[classId] ?: 0) + 1
        nextTrackNumber[classId] = number
        return "${classKeys[classId]}-$number"
    }

    private fun validBox(box: FloatArray): Boolean =
        box.size == 4 && box.all { it.isFinite() } && box[2] > box[0] && box[3] > box[1]

    private fun iou(one: FloatArray, two: FloatArray): Float {
        if (!validBox(one) || !validBox(two)) return 0f
        val left = max(one[0], two[0])
        val top = max(one[1], two[1])
        val right = kotlin.math.min(one[2], two[2])
        val bottom = kotlin.math.min(one[3], two[3])
        val intersection = max(0f, right - left) * max(0f, bottom - top)
        val areaOne = (one[2] - one[0]) * (one[3] - one[1])
        val areaTwo = (two[2] - two[0]) * (two[3] - two[1])
        val union = areaOne + areaTwo - intersection
        return if (union <= 0f) 0f else intersection / union
    }

    private fun distanceFraction(x1: Float, y1: Float, x2: Float, y2: Float, width: Int, height: Int): Float {
        val dx = (x2 - x1) / width
        val dy = (y2 - y1) / height
        return kotlin.math.sqrt(dx * dx + dy * dy)
    }

    private fun directionFor(normalizedX: Float): String = when {
        normalizedX < 0.33f -> "left"
        normalizedX > 0.67f -> "right"
        else -> "front"
    }

    private fun directionName(direction: String): String = when (direction) {
        "left" -> "左侧"
        "right" -> "右侧"
        else -> "前方"
    }

    private fun median(values: List<Float>): Float {
        if (values.isEmpty()) return 0f
        val sorted = values.sorted()
        val middle = sorted.size / 2
        return if (sorted.size % 2 == 0) {
            (sorted[middle - 1] + sorted[middle]) / 2f
        } else {
            sorted[middle]
        }
    }

    private companion object {
        const val MIN_CONFIDENCE = 0.25f
        const val STALE_TRACK_MS = 1_500L
        const val MAX_OBSERVATION_GAP_MS = 750L
        const val HISTORY_SIZE = 10
        const val GROWTH_WINDOW = 6
        const val MIN_GROWTH_SAMPLES = 3
        const val ROUTE_CONFIRM_FRAMES = 2
        const val PREDICTION_HORIZON_SECONDS = 0.5f
        const val LATERAL_ENTRY_THRESHOLD_PER_SECOND = 0.04f
        const val LATERAL_EXIT_THRESHOLD_PER_SECOND = 0.2f
        const val URGENT_AREA_FRACTION = 0.06f
        const val EARLY_URGENT_AREA_FRACTION = URGENT_AREA_FRACTION * 0.70f
        const val DANGER_HOLD_AREA_FRACTION = URGENT_AREA_FRACTION * 0.45f
        const val WARNING_HOLD_AREA_FRACTION = 0.005f
        const val CLOSE_ROUTE_AREA_FRACTION = 0.04f
        const val MAX_SHRINK_RATE_FOR_APPROACH = 0.15f
        val CLASS_NAMES = mapOf(0 to "行人", 1 to "自行车", 2 to "汽车", 3 to "摩托车", 5 to "公交车", 7 to "卡车")
        val CLASS_KEYS = mapOf(0 to "person", 1 to "bicycle", 2 to "car", 3 to "motorcycle", 5 to "bus", 7 to "truck")
        // The phone candidate has four broad traffic classes. Apply the same
        // route and temporal risk rules to each class so an obstacle that
        // blocks the walking corridor can be announced as well.
        val TWO_WHEELER_NAMES = mapOf(
            0 to "行人",
            1 to "两轮车",
            2 to "三轮车",
            3 to "四轮车",
        )
        val TWO_WHEELER_KEYS = mapOf(
            0 to "pedestrian",
            1 to "two-wheeler",
            2 to "three-wheeler",
            3 to "four-wheeler",
        )
        val FeedbackPriority.contractName: String
            get() = when (this) {
                FeedbackPriority.LOW -> "low"
                FeedbackPriority.WARNING -> "warning"
                FeedbackPriority.URGENT -> "urgent"
            }
    }

    private val classNames: Map<Int, String>
        get() = if (twoWheelerMode) TWO_WHEELER_NAMES else CLASS_NAMES

    private val classKeys: Map<Int, String>
        get() = if (twoWheelerMode) TWO_WHEELER_KEYS else CLASS_KEYS

    private val strictRouteMode: Boolean
        get() = minObservations >= 2
}
