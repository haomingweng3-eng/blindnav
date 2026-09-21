package com.blindnav.mobile.feedback

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FeedbackReportParserTest {
    @Test
    fun parsesOnlyAlertsWithValidFeedback() {
        val report = """
            {"alerts":[
              {"frame":10,"track_id":"t-1","feedback":{"priority":"warning","vibration_ms":[120,70,120],"tone":"warning","speech":"注意，前方自行车","speech_delay_ms":250}},
              {"frame":11,"track_id":"t-2","feedback":null},
              {"frame":12,"track_id":"t-3","feedback":{"priority":"bad","vibration_ms":[80],"tone":null,"speech":null,"speech_delay_ms":null}}
            ]}
        """.trimIndent()

        val parsed = FeedbackReportParser.parse(report)

        assertEquals(1, parsed.size)
        assertEquals("t-1", parsed[0].trackId)
        assertEquals(FeedbackPriority.WARNING, parsed[0].action.priority)
    }

    @Test
    fun malformedTopLevelReportProducesNoHardwareActions() {
        val parsed = FeedbackReportParser.parse("{\"alerts\":{}}")

        assertTrue(parsed.isEmpty())
    }

    @Test
    fun fractionalDurationsAreRejectedInsteadOfTruncated() {
        val report = """
            {"alerts":[
              {"track_id":"t-1","feedback":{"priority":"warning","vibration_ms":[120.5],"tone":"warning","speech":"注意","speech_delay_ms":0}}
            ]}
        """.trimIndent()

        assertTrue(FeedbackReportParser.parse(report).isEmpty())
    }
}
