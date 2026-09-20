package com.blindnav.mobile.feedback

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FeedbackActionTest {
    @Test
    fun validContractIsAccepted() {
        val action = FeedbackAction.fromContract(
            priority = "warning",
            vibrationMs = listOf(120, 70, 120),
            tone = "warning",
            speech = "注意，前方自行车",
            speechDelayMs = 250,
        )

        assertEquals(FeedbackPriority.WARNING, action?.priority)
        assertEquals(listOf(120L, 70L, 120L), action?.vibrationMs)
        assertEquals(250L, action?.speechDelayMs)
    }

    @Test
    fun malformedContractIsRejectedWithoutExecutingAnything() {
        assertNull(
            FeedbackAction.fromContract(
                priority = "warning",
                vibrationMs = emptyList(),
                tone = "warning",
                speech = "注意",
                speechDelayMs = 250,
            ),
        )
        assertNull(
            FeedbackAction.fromContract(
                priority = "unknown",
                vibrationMs = listOf(120),
                tone = null,
                speech = null,
                speechDelayMs = null,
            ),
        )
    }
}
