package com.blindnav.mobile.feedback

/** The validated, platform-neutral part of one Python risk alert feedback object. */
enum class FeedbackPriority {
    LOW,
    WARNING,
    URGENT,
}

class FeedbackAction private constructor(
    val priority: FeedbackPriority,
    val vibrationMs: List<Long>,
    val tone: String?,
    val speech: String?,
    val speechDelayMs: Long?,
) {
    companion object {
        /** Returns null for malformed input so a bad report cannot trigger hardware. */
        fun fromContract(
            priority: String?,
            vibrationMs: List<Int>?,
            tone: String?,
            speech: String?,
            speechDelayMs: Int?,
        ): FeedbackAction? {
            val parsedPriority = when (priority) {
                "low" -> FeedbackPriority.LOW
                "warning" -> FeedbackPriority.WARNING
                "urgent" -> FeedbackPriority.URGENT
                else -> return null
            }
            if (vibrationMs.isNullOrEmpty() || vibrationMs.any { it <= 0 }) return null
            if (tone !in setOf(null, "warning", "danger")) return null
            if (speech != null && speech.isBlank()) return null
            if (speechDelayMs != null && speechDelayMs < 0) return null
            return FeedbackAction(
                priority = parsedPriority,
                vibrationMs = vibrationMs.map(Int::toLong),
                tone = tone,
                speech = speech,
                speechDelayMs = speechDelayMs?.toLong(),
            )
        }
    }
}
