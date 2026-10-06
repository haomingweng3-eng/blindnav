package com.blindnav.mobile

import com.blindnav.mobile.risk.TemporalRiskEngine

/** One configuration shared by the live phone path and recorded-video replay. */
object TwoWheelerRuntimeConfig {
    const val MODEL_ASSET = "two_wheeler_candidate_320.onnx"
    const val INPUT_SIZE = 320
    // Keep low-confidence candidates available for existing-track recovery;
    // the risk engine only allows the higher floor to create a new track.
    const val CONFIDENCE = 0.10f
    const val NEW_TRACK_CONFIDENCE = 0.25f
    // The 320 model occasionally emits two boxes for the same rider with
    // IoU around 0.64. Suppress that duplicate before tracking so one rider
    // cannot split into alternating IDs and flash the risk state.
    const val NMS_IOU = 0.6f

    fun createRiskEngine() = TemporalRiskEngine(
        loomingThresholdPerSecond = 0.5f,
        urgentThresholdPerSecond = 1.2f,
        twoWheelerMode = true,
        minConfidence = CONFIDENCE,
        minNewTrackConfidence = NEW_TRACK_CONFIDENCE,
        minObservations = 2,
        minApproachArea = 0.005f,
        approachVerticalThresholdPerSecond = 0.09f,
        // Use the contact-point corridor, not any box edge, for the initial
        // route decision. This keeps parking rows outside the walking lane.
        corridorHalfWidth = 0.14f,
        // Targets behind a hedge or parked-car row have a high box but no
        // road contact point; do not let them create a route warning.
        minRoadContactY = 0.38f,
        routeBlockedWarning = true,
        earlyUrgentTimeToCloseSeconds = 1.2f,
    )
}
