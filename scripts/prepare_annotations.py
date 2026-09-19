"""从检测报告元数据生成待人工填写的事件标注模板。"""

import argparse
import json
from pathlib import Path


def build_annotation(report):
    fps = report.get("fps")
    total_frames = report.get("total_frames")
    if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps <= 0:
        raise ValueError("报告缺少正数 fps")
    if not isinstance(total_frames, int) or total_frames <= 0:
        raise ValueError("报告缺少正整数 total_frames")
    video = report.get("video")
    video_id = Path(video).stem if video else "未命名视频"
    return {
        "video_id": video_id,
        "annotation_complete": False,
        "fps": float(fps),
        "duration_s": round(total_frames / float(fps), 4),
        "events": [],
        "notes": "请填写 events 后把 annotation_complete 改为 true，再运行事件评估。",
    }


def prepare_directory(reports_dir, annotations_dir, overwrite=False):
    reports_dir = Path(reports_dir)
    annotations_dir = Path(annotations_dir)
    annotations_dir.mkdir(parents=True, exist_ok=True)
    created = []
    skipped = []
    failed = []
    for report_path in sorted(reports_dir.glob("*.json")):
        if report_path.name == "summary.json":
            continue
        target = annotations_dir / report_path.name
        if target.exists() and not overwrite:
            skipped.append(str(target))
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            annotation = build_annotation(report)
            target.write_text(
                json.dumps(annotation, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            created.append(str(target))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failed.append({"report": str(report_path), "error": str(exc)})
    return {"created": created, "skipped": skipped, "failed": failed}


def main():
    parser = argparse.ArgumentParser(description="从风险报告生成事件标注模板")
    parser.add_argument("reports_dir", help="风险报告目录")
    parser.add_argument("annotations_dir", help="标注模板输出目录")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有模板")
    args = parser.parse_args()
    result = prepare_directory(args.reports_dir, args.annotations_dir, args.overwrite)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
