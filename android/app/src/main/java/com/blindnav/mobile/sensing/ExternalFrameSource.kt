package com.blindnav.mobile.sensing

/**
 * Transport-neutral adapter for a chest camera or other external sensor.
 * USB/Wi-Fi code should decode its transport and call push(); it must not
 * bypass the same sequence validation used by the phone camera path.
 */
class ExternalFrameSource(
    private val onRejected: (FrameRejection) -> Unit = {},
) : FrameSource {
    override val kind: SourceKind = SourceKind.EXTERNAL_CAMERA

    private val validator = FrameSequenceValidator()
    private var listener: ((FramePacket) -> Unit)? = null

    override fun start(listener: (FramePacket) -> Unit) {
        check(this.listener == null) { "External camera source is already running" }
        this.listener = listener
    }

    fun push(packet: FramePacket) {
        require(packet.source == SourceKind.EXTERNAL_CAMERA) {
            "External source received a non-external frame"
        }
        val validation = validator.validate(packet)
        if (validation.accepted) {
            listener?.invoke(packet)
        } else {
            onRejected(requireNotNull(validation.rejection))
        }
    }

    override fun stop() {
        listener = null
        validator.reset()
    }
}
