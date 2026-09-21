package com.blindnav.mobile.inference

import com.blindnav.mobile.sensing.FramePacket
import com.blindnav.mobile.sensing.SourceKind
import org.junit.Assert.assertEquals
import org.junit.Test

class InferencePipelineTest {
    @Test
    fun forwardsOwnedRgbFrameToDetectorWithSourceMetadata() {
        val frame = RgbFrame(1, 1, byteArrayOf(1, 2, 3))
        val detector = Detector { listOf(Detection(1, 0.9f, floatArrayOf(0f, 0f, 1f, 1f))) }
        val results = mutableListOf<FrameDetections>()
        val pipeline = InferencePipeline(detector, results::add)

        pipeline.onFrame(
            FramePacket(SourceKind.PHONE_CAMERA, 7, 1234, 1, 1, "camera2", 0, frame)
        )

        assertEquals(1, results.size)
        assertEquals(7L, results[0].sourceFrame)
        assertEquals(1234L, results[0].captureTsMs)
        assertEquals(1, results[0].frameWidth)
        assertEquals(1, results[0].frameHeight)
        assertEquals(true, results[0].processingMs >= 0L)
        assertEquals(1, results[0].detections.size)
    }
}
