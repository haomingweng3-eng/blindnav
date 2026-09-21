package com.blindnav.mobile.inference

/** Applies CameraX's clockwise display rotation to an owned RGB frame. */
object RgbFrameRotator {
    fun rotate(source: RgbFrame, clockwiseDegrees: Int): RgbFrame {
        require(clockwiseDegrees in setOf(0, 90, 180, 270)) {
            "Camera rotation must be 0, 90, 180 or 270 degrees"
        }
        require(source.rgb.size == source.width * source.height * 3)
        if (clockwiseDegrees == 0) return source

        val targetWidth = if (clockwiseDegrees == 90 || clockwiseDegrees == 270) source.height else source.width
        val targetHeight = if (clockwiseDegrees == 90 || clockwiseDegrees == 270) source.width else source.height
        val output = ByteArray(source.rgb.size)
        for (sourceY in 0 until source.height) {
            for (sourceX in 0 until source.width) {
                val (targetX, targetY) = when (clockwiseDegrees) {
                    90 -> source.height - 1 - sourceY to sourceX
                    180 -> source.width - 1 - sourceX to source.height - 1 - sourceY
                    else -> sourceY to source.width - 1 - sourceX
                }
                val sourceOffset = (sourceY * source.width + sourceX) * 3
                val targetOffset = (targetY * targetWidth + targetX) * 3
                source.rgb.copyInto(output, targetOffset, sourceOffset, sourceOffset + 3)
            }
        }
        return RgbFrame(targetWidth, targetHeight, output)
    }
}
