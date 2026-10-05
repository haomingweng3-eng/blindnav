#!/usr/bin/env python3
"""Static guard for the Android input contract when Android SDK is unavailable."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android"


def main() -> int:
    required = {
        "settings": ANDROID / "settings.gradle.kts",
        "app_build": ANDROID / "app/build.gradle.kts",
        "manifest": ANDROID / "app/src/main/AndroidManifest.xml",
        "frame_contract": ANDROID / "app/src/main/java/com/blindnav/mobile/sensing/FrameSource.kt",
        "phone_source": ANDROID / "app/src/main/java/com/blindnav/mobile/sensing/PhoneCameraFrameSource.kt",
        "yuv_converter": ANDROID / "app/src/main/java/com/blindnav/mobile/inference/Yuv420RgbConverter.kt",
        "rgb_rotator": ANDROID / "app/src/main/java/com/blindnav/mobile/inference/RgbFrameRotator.kt",
        "yolo_decoder": ANDROID / "app/src/main/java/com/blindnav/mobile/inference/YoloOutputDecoder.kt",
        "onnx_detector": ANDROID / "app/src/main/java/com/blindnav/mobile/inference/OnnxYoloDetector.kt",
        "rider_gate": ANDROID / "app/src/main/java/com/blindnav/mobile/inference/RiderGateDetector.kt",
        "inference_pipeline": ANDROID / "app/src/main/java/com/blindnav/mobile/inference/InferencePipeline.kt",
        "background_motion": ANDROID / "app/src/main/java/com/blindnav/mobile/inference/BackgroundMotionEstimator.kt",
        "risk_engine": ANDROID / "app/src/main/java/com/blindnav/mobile/risk/TemporalRiskEngine.kt",
        "guidance_engine": ANDROID / "app/src/main/java/com/blindnav/mobile/guidance/GuidanceEngine.kt",
        "walkable_region": ANDROID / "app/src/main/java/com/blindnav/mobile/guidance/WalkableRegion.kt",
        "model_asset": ANDROID / "app/src/main/assets/yolov8n.onnx",
        "two_wheeler_asset": ANDROID / "app/src/main/assets/two_wheeler_candidate.onnx",
        "two_wheeler_fast_asset": ANDROID / "app/src/main/assets/two_wheeler_candidate_320.onnx",
        "external_source": ANDROID / "app/src/main/java/com/blindnav/mobile/sensing/ExternalFrameSource.kt",
        "feedback_action": ANDROID / "app/src/main/java/com/blindnav/mobile/feedback/FeedbackAction.kt",
        "feedback_dispatcher": ANDROID / "app/src/main/java/com/blindnav/mobile/feedback/FeedbackDispatcher.kt",
        "feedback_parser": ANDROID / "app/src/main/java/com/blindnav/mobile/feedback/FeedbackReportParser.kt",
        "frame_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/sensing/FrameSourceTest.kt",
        "external_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/sensing/ExternalFrameSourceTest.kt",
        "feedback_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/feedback/FeedbackActionTest.kt",
        "feedback_parser_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/feedback/FeedbackReportParserTest.kt",
        "feedback_admission_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/feedback/FeedbackAdmissionTest.kt",
        "rgb_rotator_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/inference/RgbFrameRotatorTest.kt",
        "risk_engine_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/risk/TemporalRiskEngineTest.kt",
        "background_motion_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/inference/BackgroundMotionEstimatorTest.kt",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        print({"passed": False, "missing": missing})
        return 1

    read = lambda path: path.read_text(encoding="utf-8")
    contract = read(required["frame_contract"])
    phone_source = read(required["phone_source"])
    external_source = read(required["external_source"])
    yuv_converter = read(required["yuv_converter"])
    yolo_decoder = read(required["yolo_decoder"])
    onnx_detector = read(required["onnx_detector"])
    rider_gate = read(required["rider_gate"])
    inference_pipeline = read(required["inference_pipeline"])
    background_motion = read(required["background_motion"])
    feedback_action = read(required["feedback_action"])
    feedback_dispatcher = read(required["feedback_dispatcher"])
    feedback_parser = read(required["feedback_parser"])
    build = read(required["app_build"])
    manifest = read(required["manifest"])
    main_activity = read(ANDROID / "app/src/main/java/com/blindnav/mobile/MainActivity.kt")
    runtime_config = read(ANDROID / "app/src/main/java/com/blindnav/mobile/TwoWheelerRuntimeConfig.kt")
    checks = {
        "source_kinds": "PHONE_CAMERA" in contract and "EXTERNAL_CAMERA" in contract,
        "timestamp_field": "captureTsMs" in contract and "captureTsMs" in phone_source,
        "camera_yuv_to_rgb": "Yuv420RgbConverter.convert" in phone_source and "data class RgbFrame" in yuv_converter,
        "camera_rotation_applied": "RgbFrameRotator.rotate" in phone_source and "rotationDegrees" in phone_source,
        "camera_async_stop_guard": "runGeneration" in phone_source and "return@addListener" in phone_source,
        "camera_analysis_resolution_bound": any(
            token in phone_source
            for token in ("setTargetResolution(Size(480, 270))", "setTargetResolution(Size(640, 360))")
        ),
        "yolo_output_decoder": "84" in yolo_decoder and "iouThreshold" in yolo_decoder,
        "onnx_runtime_detector": "onnxruntime" in build and "createSession" in onnx_detector,
        "two_wheeler_gate": all(token in rider_gate for token in ("personConfidence", "minOverlap", "TWO_WHEELER_CLASS_ID")),
        "inference_pipeline": "class InferencePipeline" in inference_pipeline and "detector.detect" in inference_pipeline,
        "inference_timing": "processingMs" in inference_pipeline and "System.nanoTime" in inference_pipeline,
        "camera_motion_compensation": all(token in background_motion for token in ("translation_consensus", "inconsistent_background", "updateRecordedGray")) and "backgroundMotion" in inference_pipeline,
        "android_temporal_risk": "loomingThresholdPerSecond" in read(required["risk_engine"]) and "FeedbackAction" in read(required["risk_engine"]),
        "android_route_prediction": all(
            token in read(required["risk_engine"])
            for token in ("approachPathConflict", "PREDICTION_HORIZON_SECONDS", "strictRouteMode")
        ),
        "android_static_target_guard": "MAX_SHRINK_RATE_FOR_APPROACH" in read(required["risk_engine"]) and "positiveApproachMotion" in read(required["risk_engine"]),
        "guidance_state_machine": all(
            token in read(required["guidance_engine"])
            for token in ("KEEP_STRAIGHT", "MOVE_LEFT", "MOVE_RIGHT", "UNKNOWN_SLOW_DOWN", "repeatMs")
        ),
        "walkable_region_contract": all(
            token in read(required["walkable_region"])
            for token in ("WalkableRegion", "WalkableRegionEstimator", "GeometryWalkableRegionEstimator")
        ),
        "model_asset_present": required["model_asset"].stat().st_size > 1_000_000,
        "two_wheeler_asset_present": required["two_wheeler_asset"].stat().st_size > 1_000_000,
        "two_wheeler_fast_asset_present": required["two_wheeler_fast_asset"].stat().st_size > 1_000_000,
        "drop_field": "droppedSinceLast" in contract and "droppedSinceLast" in phone_source,
        "external_push_validation": "fun push" in external_source and "validator.validate" in external_source,
        "camera_x": "androidx.camera:camera-camera2" in build,
        "camera_permission": "android.permission.CAMERA" in manifest,
        "vibration_permission": "android.permission.VIBRATE" in manifest,
        "tests_cover_rewind": "rejectsFrameNumberRewind" in read(required["frame_tests"]),
        "external_tests_cover_rewind": "reportsRewoundFrame" in read(required["external_tests"]),
        "feedback_contract_validation": "fromContract" in feedback_action and "malformed input" in feedback_action,
        "feedback_hardware_dispatch": all(
            token in feedback_dispatcher
            for token in ("Vibrator", "ToneGenerator", "TextToSpeech", "SPEECH_DEDUPE_WINDOW_MS")
        ),
        "feedback_report_parser": "FeedbackReportParser" in feedback_parser and "optJSONArray" in feedback_parser,
        "feedback_self_test_wired": "runFeedbackSelfTest" in main_activity and "FeedbackDispatcher" in main_activity,
        "phone_uses_single_two_wheeler_model": (
            'MODEL_ASSET = "two_wheeler_candidate_320.onnx"' in runtime_config
            and "TwoWheelerRuntimeConfig.createRiskEngine" in main_activity
            and "RiderGateDetector" not in main_activity
            and "personStride = 2" not in main_activity
        ),
        "onnx_provider_fallback": all(
            token in onnx_detector for token in ("addNnapi", "addXnnpack", "CPU_THREADS")
        ),
        "feedback_report_replay_entry": "EXTRA_RISK_REPORT_JSON" in main_activity and "dispatchReport" in main_activity,
        "feedback_tests_present": "malformedContractIsRejected" in read(required["feedback_tests"]),
        "feedback_parser_tests_present": "parsesOnlyAlertsWithValidFeedback" in read(required["feedback_parser_tests"]),
        "feedback_admission_tests_present": "AllowsUrgentEscalation" in read(required["feedback_admission_tests"]),
        "camera_rotation_tests_present": "rotatesClockwiseAndSwapsDimensions" in read(required["rgb_rotator_tests"]),
        "risk_engine_tests_present": "growingCentralTargetProducesWarningFeedback" in read(required["risk_engine_tests"]),
        "camera_motion_tests_present": all(token in read(required["background_motion_tests"]) for token in ("acceptsDistributedTranslation", "refusesFlatImage")),
    }
    failed = [name for name, passed in checks.items() if not passed]
    result = {"passed": not failed, "checks": checks, "failed": failed}
    print(result)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
