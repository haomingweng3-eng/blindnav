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
        "external_source": ANDROID / "app/src/main/java/com/blindnav/mobile/sensing/ExternalFrameSource.kt",
        "frame_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/sensing/FrameSourceTest.kt",
        "external_tests": ANDROID / "app/src/test/java/com/blindnav/mobile/sensing/ExternalFrameSourceTest.kt",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        print({"passed": False, "missing": missing})
        return 1

    contract = required["frame_contract"].read_text()
    phone_source = required["phone_source"].read_text()
    external_source = required["external_source"].read_text()
    build = required["app_build"].read_text()
    checks = {
        "source_kinds": "PHONE_CAMERA" in contract and "EXTERNAL_CAMERA" in contract,
        "timestamp_field": "captureTsMs" in contract and "captureTsMs" in phone_source,
        "drop_field": "droppedSinceLast" in contract and "droppedSinceLast" in phone_source,
        "external_push_validation": "fun push" in external_source and "validator.validate" in external_source,
        "camera_x": "androidx.camera:camera-camera2" in build,
        "camera_permission": "android.permission.CAMERA" in required["manifest"].read_text(),
        "tests_cover_rewind": "rejectsFrameNumberRewind" in required["frame_tests"].read_text(),
        "external_tests_cover_rewind": "reportsRewoundFrame" in required["external_tests"].read_text(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    result = {"passed": not failed, "checks": checks, "failed": failed}
    print(result)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
