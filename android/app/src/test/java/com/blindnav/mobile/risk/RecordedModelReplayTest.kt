package com.blindnav.mobile.risk

import com.blindnav.mobile.TwoWheelerRuntimeConfig
import com.blindnav.mobile.inference.FrameDetections
import com.blindnav.mobile.inference.BackgroundMotionEstimator
import com.blindnav.mobile.inference.YoloOutputDecoder
import com.blindnav.mobile.guidance.GeometryWalkableRegionEstimator
import com.blindnav.mobile.guidance.GuidanceEngine
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/** Optional, real model-output replay; no labels, phone or feedback hardware. */
class RecordedModelReplayTest {
    @Test
    fun replayRecordedOnnxOutputsThroughPhoneDecoderAndRiskEngine() {
        val fixturePaths = System.getenv("BLINDNAV_REPLAY_FIXTURES")?.lines()?.filter { it.isNotBlank() }
            ?: listOfNotNull(System.getenv("BLINDNAV_REPLAY_FIXTURE"))
        assumeTrue("Provide recorded output fixtures to run offline replay", fixturePaths.isNotEmpty())
        fixturePaths.forEach(::replayFixture)
    }

    private fun replayFixture(fixturePath: String) {
        val fixture = JSONObject(File(fixturePath).readText(Charsets.UTF_8))
        assertEquals(TwoWheelerRuntimeConfig.MODEL_ASSET, fixture.getString("model_asset"))
        assertEquals(TwoWheelerRuntimeConfig.INPUT_SIZE, fixture.getInt("input_size"))
        val modelHash = MessageDigest.getInstance("SHA-256").digest(File(fixture.getString("model")).readBytes())
            .joinToString("") { "%02x".format(it) }
        assertEquals(fixture.getString("model_sha256"), modelHash)
        val rawFile = File(fixture.getString("raw_file"))
        val frames = fixture.getJSONArray("frames")
        val rawCount = fixture.getInt("channels") * fixture.getInt("candidates")
        assertEquals(frames.length().toLong() * rawCount * 4, rawFile.length())
        val engine = TwoWheelerRuntimeConfig.createRiskEngine()
        val guidanceEngine = GuidanceEngine()
        val regionEstimator = GeometryWalkableRegionEstimator()
        val motionEstimator = BackgroundMotionEstimator()
        val stride = fixture.optInt("sample_stride", 1)
        require(stride > 0)
        val grayStream = if (fixture.has("gray_file")) File(fixture.getString("gray_file")).inputStream().buffered() else null
        val grayBytes = ByteArray(fixture.optInt("gray_width", 0) * fixture.optInt("gray_height", 0))
        if (grayStream != null) {
            assertEquals(frames.length().toLong() * grayBytes.size, File(fixture.getString("gray_file")).length())
        }
        val output = JSONArray()
        try { rawFile.inputStream().buffered().use { stream ->
            val bytes = ByteArray(rawCount * 4)
            for (i in 0 until frames.length()) {
                var read = 0
                while (read < bytes.size) {
                    val count = stream.read(bytes, read, bytes.size - read)
                    check(count > 0) { "Truncated ONNX output" }
                    read += count
                }
                if (grayStream != null) {
                    var grayRead = 0
                    while (grayRead < grayBytes.size) {
                        val count = grayStream.read(grayBytes, grayRead, grayBytes.size - grayRead)
                        check(count > 0) { "Truncated background pixels" }
                        grayRead += count
                    }
                }
                if (i % stride != 0) continue
                val raw = FloatArray(rawCount)
                ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(raw)
                val meta = frames.getJSONObject(i)
                val width = meta.getInt("width")
                val height = meta.getInt("height")
                val detections = YoloOutputDecoder.decode(
                    raw, fixture.getInt("candidates"), width, height,
                    meta.getDouble("ratio").toFloat(),
                    meta.getDouble("pad_left").toFloat(), meta.getDouble("pad_top").toFloat(),
                    TwoWheelerRuntimeConfig.CONFIDENCE, TwoWheelerRuntimeConfig.NMS_IOU,
                )
                val motionStarted = System.nanoTime()
                val motion = if (grayStream != null) motionEstimator.updateRecordedGray(
                    fixture.getInt("gray_width"), fixture.getInt("gray_height"), grayBytes,
                    width, height, meta.getLong("timestamp_ms"), detections,
                ) else null
                val motionMs = (System.nanoTime() - motionStarted) / 1_000_000.0
                // CameraX numbers analyzed frames, not the frames it dropped.
                val frame = FrameDetections((i / stride).toLong(), meta.getLong("timestamp_ms"), width, height,
                    detections = detections, backgroundMotion = motion)
                val alerts = engine.update(frame)
                val guidance = guidanceEngine.update(
                    frame,
                    regionEstimator.estimate(frame),
                    engine.currentTracks,
                    alerts,
                )
                val tracksJson = JSONArray()
                engine.currentTracks.forEach { track ->
                    val history = JSONArray()
                    track.roadHistory.forEach { history.put(JSONObject().put("x", it.x).put("y", it.y).put("timestamp_ms", it.timestampMs)) }
                    tracksJson.put(JSONObject().put("track_id", track.trackId)
                        .put("box", JSONArray(track.box.toList())).put("risk_level", track.riskLevel).put("history", history))
                }
                val alertsJson = JSONArray()
                alerts.forEach { alert ->
                    alertsJson.put(JSONObject().put("track_id", alert.trackId).put("priority", alert.feedback.priority.name)
                        .put("speech", alert.feedback.speech).put("looming_per_second", alert.loomingPerSecond))
                }
                val record = JSONObject().put("source_frame", meta.getInt("source_frame"))
                    .put("timestamp_ms", frame.captureTsMs).put("detection_count", detections.size)
                    .put("tracks", tracksJson).put("alerts", alertsJson)
                    .put("guidance_state", guidance.state.name)
                    .put("guidance_reason", guidance.reason)
                    .put("guidance_confidence", guidance.confidence)
                if (motion != null) record.put("background_motion", JSONObject()
                    .put("reliable", motion.reliable).put("dx_pixels", motion.dxPixels).put("dy_pixels", motion.dyPixels)
                    .put("matches", motion.matches).put("inliers", motion.inliers).put("reason", motion.reason)
                    .put("desktop_ms", motionMs))
                output.put(record)
            }
        } } finally { grayStream?.close() }
        File(fixture.getString("trace_file")).writeText(
            JSONObject().put("model_sha256", fixture.getString("model_sha256"))
                .put("config", "TwoWheelerRuntimeConfig").put("frames", output)
                .put("phone_performance_measured", false).toString(2), Charsets.UTF_8,
        )
    }
}
