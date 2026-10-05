"""Inspect semantic road bounds against frozen detections; no truth writes."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

import cv2
import numpy as np

try:
    from .walkable_region import SegformerWalkableRegionEstimator
except ImportError:
    from walkable_region import SegformerWalkableRegionEstimator


def inspect(video, report, output, frames, estimator=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    payload = json.loads(Path(report).read_text(encoding="utf-8"))
    estimator = estimator or SegformerWalkableRegionEstimator()
    by_frame = {}
    for record in payload["records"]:
        by_frame.setdefault(record["frame"], []).append(record)
    cap = cv2.VideoCapture(str(video))
    results = []
    try:
        for index in frames:
            # Detection reports are 1-based; OpenCV positions are 0-based.
            cap.set(cv2.CAP_PROP_POS_FRAMES, index - 1)
            ok, original = cap.read()
            if not ok:
                raise RuntimeError(f"Cannot read frame {index}: {video}")
            started = time.perf_counter()
            region = estimator.estimate(original)
            seconds = time.perf_counter() - started
            height, width = original.shape[:2]
            scale = min(960 / width, 540 / height)
            vis = cv2.resize(original, (round(width*scale), round(height*scale)))
            h, w = vis.shape[:2]
            rows = region.row_bounds
            if rows:
                polygon = [(int(left*w), int(y*h)) for y, left, right in rows]
                polygon += [(int(right*w), int(y*h)) for y, left, right in reversed(rows)]
                overlay = vis.copy()
                cv2.fillPoly(overlay, [np.asarray(polygon, np.int32)], (160, 100, 0))
                vis = cv2.addWeighted(overlay, .22, vis, .78, 0)
                cv2.polylines(vis, [np.asarray(polygon, np.int32)], True, (255, 180, 0), 2)
            cv2.rectangle(vis, (int(region.route_left*w), int(region.floor_y*h)),
                          (int(region.route_right*w), h-1), (255, 255, 0), 1)
            observations = []
            for record in by_frame.get(index, []):
                x1, y1, x2, y2 = record["box"]
                contact = ((x1+x2)/2/width, y2/height)
                inside = region.contains(*contact)
                color = (0, 180, 255) if inside else (160, 160, 160)
                cv2.rectangle(vis, (int(x1*scale), int(y1*scale)),
                              (int(x2*scale), int(y2*scale)), color, 2)
                cv2.circle(vis, (int(contact[0]*w), int(contact[1]*h)), 4, color, -1)
                observations.append({"track_id": record["track_id"], "conf": record["conf"],
                                     "contact": contact, "central_route_contact": inside})
            cv2.putText(vis, f"frame {index} | {region.surface} | {region.source}",
                        (12, 25), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 2)
            cv2.putText(vis, "BLUE road extent | CYAN intended route | ORANGE contact inside",
                        (12, h-14), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
            target = output / f"frame_{index:04d}.jpg"
            cv2.imwrite(str(target), vis)
            results.append({"frame": index, "region": asdict(region), "elapsed_s": seconds,
                            "image": str(target.resolve()), "contacts": observations,
                            "load_error": estimator.load_error, "inference_error": estimator.inference_error})
    finally:
        cap.release()
    result = {"video": str(video), "detection_report": str(report), "frames": results,
              "offline_only": True, "phone_performance_verified": False, "training_truth": False}
    (output / "inspection.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("report")
    parser.add_argument("output")
    parser.add_argument("--frames", type=int, nargs="+", required=True)
    args = parser.parse_args()
    result = inspect(args.video, args.report, args.output, args.frames)
    print(json.dumps({"frames": len(result["frames"]), "output": args.output,
                      "sources": [item["region"]["source"] for item in result["frames"]]}))
