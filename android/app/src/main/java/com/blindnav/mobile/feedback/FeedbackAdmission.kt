package com.blindnav.mobile.feedback

/** Bounded repeat suppression for all feedback channels, with immediate escalation. */
class FeedbackAdmission(private val repeatWindowMs: Long = 1_000L) {
    private data class Record(val priority: FeedbackPriority, val timestampMs: Long)
    private val records = mutableMapOf<String, Record>()
    private var urgentAtMs: Long? = null

    fun accept(trackId: String, priority: FeedbackPriority, nowMs: Long): Boolean {
        records.entries.removeAll { nowMs - it.value.timestampMs > 10_000L }
        if (priority != FeedbackPriority.URGENT && urgentAtMs?.let { nowMs - it in 0 until repeatWindowMs } == true) return false
        val previous = records[trackId]
        if (previous != null && nowMs - previous.timestampMs in 0 until repeatWindowMs &&
            priority.ordinal <= previous.priority.ordinal
        ) return false
        records[trackId] = Record(priority, nowMs)
        if (priority == FeedbackPriority.URGENT) urgentAtMs = nowMs
        return true
    }

    fun reset() {
        records.clear()
        urgentAtMs = null
    }
}
