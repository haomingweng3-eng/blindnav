package com.blindnav.mobile.sensing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExternalFrameSourceTest {
    private fun packet(frame: Long, timestamp: Long) = FramePacket(
        source = SourceKind.EXTERNAL_CAMERA,
        sourceFrame = frame,
        captureTsMs = timestamp,
        width = 1280,
        height = 720,
        transport = "wifi",
        droppedSinceLast = 0,
        payload = ByteArray(0),
    )

    @Test
    fun forwardsOnlyValidatedExternalFrames() {
        val received = mutableListOf<FramePacket>()
        val source = ExternalFrameSource()
        source.start(received::add)

        source.push(packet(1, 100))
        source.push(packet(2, 133))

        assertEquals(listOf(1L, 2L), received.map { it.sourceFrame })
    }

    @Test
    fun reportsRewoundFrameAndDoesNotForwardIt() {
        val received = mutableListOf<FramePacket>()
        val rejected = mutableListOf<FrameRejection>()
        val source = ExternalFrameSource(rejected::add)
        source.start(received::add)

        source.push(packet(2, 100))
        source.push(packet(1, 133))

        assertEquals(1, received.size)
        assertTrue(rejected.contains(FrameRejection.FRAME_NUMBER_REWIND))
    }

    @Test
    fun stopResetsSequenceForTheNextRun() {
        val source = ExternalFrameSource()
        val received = mutableListOf<FramePacket>()
        source.start(received::add)
        source.push(packet(8, 100))
        source.stop()
        source.start(received::add)

        source.push(packet(0, 10))

        assertEquals(2, received.size)
    }
}
