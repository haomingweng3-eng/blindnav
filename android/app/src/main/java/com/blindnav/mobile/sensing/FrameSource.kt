package com.blindnav.mobile.sensing

/** A camera-independent input contract shared by phone and external sensors. */
interface FrameSource {
    val kind: SourceKind
    fun start(listener: (FramePacket) -> Unit)
    fun stop()
}

enum class SourceKind {
    PHONE_CAMERA,
    EXTERNAL_CAMERA,
}

data class FramePacket(
    val source: SourceKind,
    val sourceFrame: Long,
    val captureTsMs: Long,
    val width: Int,
    val height: Int,
    val transport: String,
    val droppedSinceLast: Int,
    /**
     * Opaque image payload owned by the concrete adapter. For CameraX this is
     * valid only during the listener callback; async consumers must copy it.
     */
    val payload: Any,
)

enum class FrameRejection {
    FRAME_NUMBER_REWIND,
    TIMESTAMP_REWIND,
    INVALID_DIMENSIONS,
    NEGATIVE_DROPPED_COUNT,
}

data class FrameValidation(val accepted: Boolean, val rejection: FrameRejection? = null)

class FrameSequenceValidator {
    private var lastFrame: Long? = null
    private var lastTimestamp: Long? = null

    fun validate(packet: FramePacket): FrameValidation {
        val previousFrame = lastFrame
        if (previousFrame != null && packet.sourceFrame <= previousFrame) {
            return FrameValidation(false, FrameRejection.FRAME_NUMBER_REWIND)
        }
        val previousTimestamp = lastTimestamp
        if (previousTimestamp != null && packet.captureTsMs <= previousTimestamp) {
            return FrameValidation(false, FrameRejection.TIMESTAMP_REWIND)
        }
        if (packet.width <= 0 || packet.height <= 0) {
            return FrameValidation(false, FrameRejection.INVALID_DIMENSIONS)
        }
        if (packet.droppedSinceLast < 0) {
            return FrameValidation(false, FrameRejection.NEGATIVE_DROPPED_COUNT)
        }
        lastFrame = packet.sourceFrame
        lastTimestamp = packet.captureTsMs
        return FrameValidation(true)
    }

    fun reset() {
        lastFrame = null
        lastTimestamp = null
    }
}
