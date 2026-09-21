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
        "inference_pipeline": ANDROID / "app/src/main/java/com/blindnav/mobile/inference/InferencePipeline.kt",
        "risk_engine": ANDROID / "app/src/main/java/com/blindnav/mobile/risk/TemporalRiskEngine.kt",
        "model_asset": ANDROID / "app/src/main/assets/yolov8n.onnx",
        "external_source": ANDROID / "app/src/main/java/com/blindnav/mobile/sensing/ExternalFrameSource.kt",
        "feedback_action": ANDROID / "app/src/main/java/com/blindnav/mobile/feedback/FeedbackAction.kt",
        "feedback_dispatcher": ANDROID / "app/src/main/java/com/blindnav/mobile/feedback/FeedbackDispatcher.kt",
        "feedback_parser": ANDROID / "app/src/main/java/com/blindnav/mobile/feedback/FeedbackReportParser.kt",
        "frame_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/sensing/FrameSourceTest.kt",
        "external_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/sensing/ExternalFrameSourceTest.kt",
        "feedback_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/feedback/FeedbackActionTest.kt",
        "feedback_parser_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/feedback/FeedbackReportParserTest.kt",
        "rgb_rotator_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/inference/RgbFrameRotatorTest.kt",
        "risk_engine_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/risk/TemporalRiskEngineTest.kt",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        print({"passed": False, "missing": missing})
        return 1

    contract = required["frame_contract"].read_text()
    phone_source = required["phone_source"].read_text()
    external_source = required["external_source"].read_text()
    yuv_converter = required["yuv_converter"].read_text()
    yolo_decoder = required["yolo_decoder"].read_text()
    onnx_detector = required["onnx_detector"].read_text()
    inference_pipeline = required["inference_pipeline"].read_text()
    feedback_action = required["feedback_action"].read_text()
    feedback_dispatcher = required["feedback_dispatcher"].read_text()
    feedback_parser = required["feedback_parser"].read_text()
    build = required["app_build"].read_text()
    manifest = required["manifest"].read_text()
    main_activity = (ANDROID / "app/src/main/java/com/blindnav/mobile/MainActivity.kt").read_text()
    checks = {
        "source_kinds": "PHONE_CAMERA" in contract and "EXTERNAL_CAMERA" in contract,
        "timestamp_field": "captureTsMs" in contract and "captureTsMs" in phone_source,
        "camera_yuv_to_rgb": "Yuv420RgbConverter.convert" in phone_source and "data class RgbFrame" in yuv_converter,
        "camera_rotation_applied": "RgbFrameRotator.rotate" in phone_source and "rotationDegrees" in phone_source,
        "yolo_output_decoder": "84" in yolo_decoder and "iouThreshold" in yolo_decoder,
        "onnx_runtime_detector": "onnxruntime" in build and "createSession" in onnx_detector,
        "inference_pipeline": "class InferencePipeline" in inference_pipeline and "detector.detect" in inference_pipeline,
        "android_temporal_risk": "loomingThresholdPerSecond" in required["risk_engine"].read_text() and "FeedbackAction" in required["risk_engine"].read_text(),
        "model_asset_present": required["model_asset"].stat().st_size > 1_000_000,
        "drop_field": "droppedSinceLast" in contract and "droppedSinceLast" in phone_source,
        "external_push_validation": "fun push" in external_source and "validator.validate" in external_source,
        "camera_x": "androidx.camera:camera-camera2" in build,
        "camera_permission": "android.permission.CAMERA" in manifest,
        "vibration_permission": "android.permission.VIBRATE" in manifest,
        "tests_cover_rewind": "rejectsFrameNumberRewind" in required["frame_tests"].read_text(),
        "external_tests_cover_rewind": "reportsRewoundFrame" in required["external_tests"].read_text(),
        "feedback_contract_validation": "fromContract" in feedback_action and "malformed input" in feedback_action,
        "feedback_hardware_dispatch": all(
            token in feedback_dispatcher
            for token in ("Vibrator", "ToneGenerator", "TextToSpeech", "SPEECH_DEDUPE_WINDOW_MS")
        ),
        "feedback_report_parser": "FeedbackReportParser" in feedback_parser and "optJSONArray" in feedback_parser,
        "feedback_self_test_wired": "runFeedbackSelfTest" in main_activity and "FeedbackDispatcher" in main_activity,
        "feedback_report_replay_entry": "EXTRA_RISK_REPORT_JSON" in main_activity and "dispatchReport" in main_activity,
        "feedback_tests_present": "malformedContractIsRejected" in required["feedback_tests"].read_text(),
        "feedback_parser_tests_present": "parsesOnlyAlertsWithValidFeedback" in required["feedback_parser_tests"].read_text(),
        "camera_rotation_tests_present": "rotatesClockwiseAndSwapsDimensions" in required["rgb_rotator_tests"].read_text(),
        "risk_engine_tests_present": "growingCentralTargetProducesWarningFeedback" in required["risk_engine_tests"].read_text(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    result = {"passed": not failed, "checks": checks, "failed": failed}
    print(result)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
