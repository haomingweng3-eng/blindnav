package com.blindnav.mobile.feedback

import org.json.JSONArray
import org.json.JSONObject

data class ParsedFeedback(
    val trackId: String,
    val action: FeedbackAction,
)

/** Parses the platform-neutral Python report without making risk decisions. */
object FeedbackReportParser {
    fun parse(reportJson: String): List<ParsedFeedback> {
        val report = runCatching { JSONObject(reportJson) }.getOrNull() ?: return emptyList()
        val alerts = report.optJSONArray("alerts") ?: return emptyList()
        return buildList {
            for (index in 0 until alerts.length()) {
                val alert = alerts.optJSONObject(index) ?: continue
                val feedback = alert.optJSONObject("feedback") ?: continue
                val action = FeedbackAction.fromContract(
                    priority = feedback.optStringOrNull("priority"),
                    vibrationMs = feedback.optIntArray("vibration_ms"),
                    tone = feedback.optStringOrNull("tone"),
                    speech = feedback.optStringOrNull("speech"),
                    speechDelayMs = feedback.optIntOrNull("speech_delay_ms"),
                ) ?: continue
                val trackId = alert.optStringOrNull("track_id") ?: continue
                add(ParsedFeedback(trackId, action))
            }
        }
    }

    private fun JSONObject.optStringOrNull(name: String): String? {
        if (!has(name) || isNull(name)) return null
        return optString(name).takeIf { it.isNotBlank() }
    }

    private fun JSONObject.optIntOrNull(name: String): Int? {
        if (!has(name) || isNull(name)) return null
        return (opt(name) as? Number)?.exactIntOrNull()
    }

    private fun JSONObject.optIntArray(name: String): List<Int>? {
        val values: JSONArray = optJSONArray(name) ?: return null
        return buildList {
            for (index in 0 until values.length()) {
                val value = values.opt(index)
                val parsed = (value as? Number)?.exactIntOrNull() ?: return null
                add(parsed)
            }
        }
    }

    private fun Number.exactIntOrNull(): Int? {
        val asDouble = toDouble()
        if (!asDouble.isFinite() || asDouble % 1.0 != 0.0) return null
        val asLong = toLong()
        return asLong.takeIf { it in Int.MIN_VALUE..Int.MAX_VALUE }?.toInt()
    }
}
