package com.blindnav.mobile.guidance

import com.blindnav.mobile.feedback.FeedbackAction
import com.blindnav.mobile.feedback.FeedbackPriority
import com.blindnav.mobile.inference.FrameDetections
import com.blindnav.mobile.risk.AndroidRiskAlert
import com.blindnav.mobile.risk.RiskTrackSnapshot

enum class GuidanceState {
    KEEP_STRAIGHT,
    MOVE_LEFT,
    MOVE_RIGHT,
    STOP,
    CAUTION,
    DANGER,
    UNKNOWN_SLOW_DOWN,
}

data class GuidanceDecision(
    val state: GuidanceState,
    val reason: String,
    val confidence: Float,
    val feedback: FeedbackAction?,
)

/** Combines local free-space, detections and temporal risk into one feedback state. */
class GuidanceEngine(
    private val repeatMs: Long = 2_500L,
) {
    private var lastFrame: Long? = null
    private var blockingStreak = 0
    private var lastState: GuidanceState? = null
    private var lastEmitMs = Long.MIN_VALUE
    private var lastWarningEmitMs = Long.MIN_VALUE
    private var lastWarningRank = 0

    fun update(
        frame: FrameDetections,
        region: WalkableRegion,
        tracks: List<RiskTrackSnapshot>,
        alerts: List<AndroidRiskAlert>,
    ): GuidanceDecision {
        val consecutive = lastFrame == null || frame.sourceFrame == lastFrame!! + 1
        val blocking = frame.detections.any { detection ->
            val box = detection.box
            box.size == 4 && box[2] > box[0] && box[3] > box[1] &&
                detection.confidence >= MIN_CONFIDENCE &&
                region.containsContact((box[0] + box[2]) / 2f / frame.frameWidth,
                    box[3] / frame.frameHeight)
        }
        blockingStreak = if (blocking && consecutive) blockingStreak + 1 else if (blocking) 1 else 0
        lastFrame = frame.sourceFrame

        val urgent = alerts.any { it.feedback.priority == FeedbackPriority.URGENT } ||
            tracks.any { it.riskLevel >= 2 }
        val warning = alerts.any { it.feedback.priority == FeedbackPriority.WARNING } ||
            tracks.any { it.riskLevel >= 1 }
        val closeBlocking = frame.detections.any { detection ->
            val box = detection.box
            box.size == 4 &&
                detection.confidence >= MIN_CONFIDENCE &&
                region.containsContact((box[0] + box[2]) / 2f / frame.frameWidth,
                    box[3] / frame.frameHeight) &&
                ((box[2] - box[0]) * (box[3] - box[1])) /
                    (frame.frameWidth.toFloat() * frame.frameHeight.toFloat()) >= CLOSE_ROUTE_AREA
        }
        // A missing or failed camera-motion estimate leaves route motion
        // ambiguous. Keep the user in the conservative state until a fresh
        // reliable estimate arrives; never announce a clear route solely
        // because the detector saw no urgent track.
        val motionUncertain = frame.backgroundMotion != null &&
            frame.backgroundMotion.reliable.not()
        val decision = when {
            urgent ->
                GuidanceDecision(GuidanceState.DANGER, "路线内持续接近", 0.9f, action("停止，前方有危险", FeedbackPriority.URGENT))
            warning || (blocking && blockingStreak >= 2) ->
                if (warning) {
                    GuidanceDecision(GuidanceState.CAUTION, "目标可能进入行走路线", 0.75f,
                        action("注意，前方可能有障碍", FeedbackPriority.WARNING))
                } else {
                    detourDecision(region) ?: GuidanceDecision(
                        GuidanceState.CAUTION, "目标可能进入行走路线", 0.75f,
                        action("注意，前方可能有障碍", FeedbackPriority.WARNING),
                    )
                }
            blocking ->
                GuidanceDecision(GuidanceState.UNKNOWN_SLOW_DOWN, "等待连续帧确认", 0.25f,
                    action("前方情况不明，请减速", FeedbackPriority.WARNING))
            motionUncertain || region.confidence < MIN_REGION_CONFIDENCE ->
                GuidanceDecision(GuidanceState.UNKNOWN_SLOW_DOWN, "可行走区域不确定", region.confidence,
                    action("前方情况不明，请减速", FeedbackPriority.WARNING))
            else -> guidanceDirection(region)
        }
        return if (shouldEmit(decision.state, frame.captureTsMs)) {
            lastState = decision.state
            lastEmitMs = frame.captureTsMs
            decision
        } else {
            decision.copy(feedback = null)
        }
    }

    fun reset() {
        lastFrame = null
        blockingStreak = 0
        lastState = null
        lastEmitMs = Long.MIN_VALUE
        lastWarningEmitMs = Long.MIN_VALUE
        lastWarningRank = 0
    }

    private fun guidanceDirection(region: WalkableRegion): GuidanceDecision = when (region.suggestedDirection) {
        GuidanceState.MOVE_LEFT -> GuidanceDecision(GuidanceState.MOVE_LEFT, "右侧空间更受阻", region.confidence,
            action("向左绕行", FeedbackPriority.LOW))
        GuidanceState.MOVE_RIGHT -> GuidanceDecision(GuidanceState.MOVE_RIGHT, "左侧空间更受阻", region.confidence,
            action("向右绕行", FeedbackPriority.LOW))
        GuidanceState.STOP -> GuidanceDecision(GuidanceState.STOP, "左右均不明确", region.confidence,
            action("停止，前方路线不明确", FeedbackPriority.URGENT))
        else -> GuidanceDecision(GuidanceState.KEEP_STRAIGHT, "中央路线可通行", region.confidence,
            action("保持直行", FeedbackPriority.LOW))
    }

    private fun detourDecision(region: WalkableRegion): GuidanceDecision? = when (region.suggestedDirection) {
        GuidanceState.MOVE_LEFT -> GuidanceDecision(GuidanceState.MOVE_LEFT, "中央路线受阻，左侧更空", region.confidence,
            action("注意，向左绕行", FeedbackPriority.WARNING))
        GuidanceState.MOVE_RIGHT -> GuidanceDecision(GuidanceState.MOVE_RIGHT, "中央路线受阻，右侧更空", region.confidence,
            action("注意，向右绕行", FeedbackPriority.WARNING))
        // Keep the established two-frame central-blocker contract as CAUTION
        // when neither side is demonstrably open. STOP is reserved for the
        // urgent risk branch or the normal direction decision above.
        GuidanceState.STOP -> null
        else -> null
    }

    private fun shouldEmit(state: GuidanceState, nowMs: Long): Boolean {
        val warningRank = warningRank(state)
        if (warningRank > 0 && lastWarningEmitMs != Long.MIN_VALUE &&
            nowMs - lastWarningEmitMs < repeatMs && warningRank <= lastWarningRank) {
            lastState = state
            return false
        }
        val emit = state != lastState || nowMs - lastEmitMs >= repeatMs
        if (emit) {
            lastState = state
            lastEmitMs = nowMs
            if (warningRank > 0) {
                lastWarningEmitMs = nowMs
                lastWarningRank = warningRank
            }
        }
        return emit
    }

    private fun warningRank(state: GuidanceState): Int = when (state) {
        GuidanceState.UNKNOWN_SLOW_DOWN -> 1
        GuidanceState.CAUTION -> 2
        GuidanceState.DANGER, GuidanceState.STOP -> 3
        else -> 0
    }

    private fun action(text: String, priority: FeedbackPriority): FeedbackAction {
        val vibration = when (priority) {
            FeedbackPriority.LOW -> listOf(70)
            FeedbackPriority.WARNING -> listOf(120, 70, 120)
            FeedbackPriority.URGENT -> listOf(260, 80, 260)
        }
        val tone = when (priority) {
            FeedbackPriority.LOW -> null
            FeedbackPriority.WARNING -> "warning"
            FeedbackPriority.URGENT -> "danger"
        }
        return FeedbackAction.fromContract(
            priority = when (priority) {
                FeedbackPriority.LOW -> "low"
                FeedbackPriority.WARNING -> "warning"
                FeedbackPriority.URGENT -> "urgent"
            },
            vibrationMs = vibration,
            tone = tone,
            speech = text,
            speechDelayMs = 0,
        ) ?: error("internal guidance feedback contract rejected")
    }

    private companion object {
        const val MIN_CONFIDENCE = 0.25f
        const val MIN_REGION_CONFIDENCE = 0.35f
        const val CLOSE_ROUTE_AREA = 0.04f
    }
}
