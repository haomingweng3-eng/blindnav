package com.blindnav.mobile.sensing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FrameSourceTest {
    private fun packet(
        frame: Long,
        timestamp: Long,
        dropped: Int = 0,
        width: Int = 640,
        height: Int = 480,
    ) = FramePacket(
        source = SourceKind.PHONE_CAMERA,
        sourceFrame = frame,
        captureTsMs = timestamp,
        width = width,
        height = height,
        transport = "camera2",
        droppedSinceLast = dropped,
        payload = Any(),
    )

    @Test
    fun acceptsIncreasingFramesAndRecordsDroppedFrames() {
        val validator = FrameSequenceValidator()

        assertTrue(validator.validate(packet(1, 100)).accepted)
        val second = validator.validate(packet(3, 166, dropped = 1))

        assertTrue(second.accepted)
    }

    @Test
    fun rejectsFrameNumberRewind() {
        val validator = FrameSequenceValidator()
        validator.validate(packet(3, 100))

        val result = validator.validate(packet(2, 133))

        assertEquals(FrameRejection.FRAME_NUMBER_REWIND, result.rejection)
    }

    @Test
    fun rejectsTimestampRewindEvenWhenFrameNumberIncreases() {
        val validator = FrameSequenceValidator()
        validator.validate(packet(3, 200))

        val result = validator.validate(packet(4, 199))

        assertEquals(FrameRejection.TIMESTAMP_REWIND, result.rejection)
    }

    @Test
    fun rejectsInvalidDimensionsAndNegativeDrops() {
        val invalidSize = FrameSequenceValidator().validate(packet(1, 100, width = 0))
        val invalidDrops = FrameSequenceValidator().validate(packet(1, 100, dropped = -1))

        assertEquals(FrameRejection.INVALID_DIMENSIONS, invalidSize.rejection)
        assertEquals(FrameRejection.NEGATIVE_DROPPED_COUNT, invalidDrops.rejection)
    }

    @Test
    fun resetAllowsAStoppedSourceToStartAtFrameZero() {
        val validator = FrameSequenceValidator()
        assertTrue(validator.validate(packet(4, 100)).accepted)

        validator.reset()

        assertTrue(validator.validate(packet(0, 10)).accepted)
    }
}
