package com.blindnav.mobile.feedback

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FeedbackAdmissionTest {
    @Test
    fun suppressesSameLevelRepeatsButAllowsUrgentEscalation() {
        val admission = FeedbackAdmission(repeatWindowMs = 1_000L)

        assertTrue(admission.accept("two-wheeler-1", FeedbackPriority.WARNING, 100L))
        assertFalse(admission.accept("two-wheeler-1", FeedbackPriority.WARNING, 500L))
        assertTrue(admission.accept("two-wheeler-1", FeedbackPriority.URGENT, 600L))
        assertFalse(admission.accept("two-wheeler-1", FeedbackPriority.WARNING, 700L))
    }

    @Test
    fun expiresOldTrackRecords() {
        val admission = FeedbackAdmission(repeatWindowMs = 1_000L)

        assertTrue(admission.accept("two-wheeler-1", FeedbackPriority.WARNING, 100L))
        assertTrue(admission.accept("two-wheeler-1", FeedbackPriority.WARNING, 1_101L))
    }
}
