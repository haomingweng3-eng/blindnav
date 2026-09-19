"""把项目的可复现仿真和交互回放证据收成一次验收检查。"""

import argparse
import json
from pathlib import Path

try:
    from .evaluate_risk_engine import run_suite
    from .feedback_contract import validate_report
    from .replay_detections import replay_detection_file
except ImportError:  # 支持直接执行 scripts/acceptance_check.py
    from evaluate_risk_engine import run_suite
    from feedback_contract import validate_report
    from replay_detections import replay_detection_file


def build_acceptance_report(fixture_path):
    """运行不依赖摄像头的核心验收，并返回可保存的 JSON 对象。"""
    suite = run_suite()
    simulation_passed = not suite["missed_expected_alerts"] and not suite["false_mid_alerts"]

    replay = replay_detection_file(Path(fixture_path))
    contract_errors = validate_report(replay)
    feedback = replay["alerts"][0].get("feedback") if replay["alerts"] else None
    replay_passed = (
        replay["alert_count"] >= 1
        and feedback is not None
        and feedback.get("priority") == "warning"
        and feedback.get("speech") == "注意，前方自行车"
    )

    return {
        "passed": simulation_passed and replay_passed,
        "simulation": {
            "passed": simulation_passed,
            "scenario_count": suite["scenario_count"],
            "missed_expected_alerts": suite["missed_expected_alerts"],
            "false_mid_alerts": suite["false_mid_alerts"],
        },
        "replay": {
            "passed": replay_passed and not contract_errors,
            "contract_passed": not contract_errors,
            "contract_errors": contract_errors,
            "fixture": str(fixture_path),
            "alert_count": replay["alert_count"],
            "speech": feedback.get("speech") if feedback else None,
            "tone": feedback.get("tone") if feedback else None,
            "vibration_ms": feedback.get("vibration_ms") if feedback else None,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="运行盲行导航核心验收检查")
    parser.add_argument(
        "fixture",
        nargs="?",
        default="tests/fixtures/synthetic_approach_detections.json",
        help="检测记录回放 fixture JSON",
    )
    parser.add_argument("-o", "--output", help="可选的验收报告 JSON 路径")
    args = parser.parse_args()

    report = build_acceptance_report(args.fixture)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
