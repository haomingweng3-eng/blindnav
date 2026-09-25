"""可复现的 YOLO 检测器微调入口。

这个脚本只消费已经完成矩形框标注的数据集 data.yaml；视频级 safe/conflict
标签不能直接作为检测训练标签。训练产物放在 runs/ 下，不提交原始视频。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_train_kwargs(
    data,
    epochs=80,
    imgsz=640,
    batch=-1,
    device=None,
    project="runs",
    name="detector_finetune",
    seed=20260926,
):
    if not str(data).strip():
        raise ValueError("data must not be empty")
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if imgsz <= 0:
        raise ValueError("imgsz must be positive")
    if batch == 0 or batch < -1:
        raise ValueError("batch must be -1 or a positive integer")
    if not str(project).strip() or not str(name).strip():
        raise ValueError("project and name must not be empty")
    kwargs = {
        "data": str(data),
        "epochs": int(epochs),
        "imgsz": int(imgsz),
        "batch": int(batch),
        "project": str(project),
        "name": str(name),
        "seed": int(seed),
        "exist_ok": False,
    }
    if device is not None:
        kwargs["device"] = str(device)
    return kwargs


def main(argv=None):
    parser = argparse.ArgumentParser(description="Train/fine-tune a YOLO detector")
    parser.add_argument("--model", default="models/yolov8n.pt")
    parser.add_argument("--data", required=True, help="人工框标注生成的 data.yaml")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=-1)
    parser.add_argument("--device", default=None, help="cuda:0、mps 或 cpu")
    parser.add_argument("--project", default="runs")
    parser.add_argument("--name", default="detector_finetune")
    parser.add_argument("--seed", type=int, default=20260926)
    args = parser.parse_args(argv)

    model_path = Path(args.model)
    data_path = Path(args.data)
    if not model_path.is_file():
        raise FileNotFoundError(f"model not found: {model_path}")
    if not data_path.is_file():
        raise FileNotFoundError(f"data yaml not found: {data_path}")

    kwargs = build_train_kwargs(
        data=data_path,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        seed=args.seed,
    )

    from ultralytics import YOLO

    model = YOLO(str(model_path))
    results = model.train(**kwargs)
    save_dir = getattr(results, "save_dir", None)
    summary = {
        "model": str(model_path),
        "data": str(data_path),
        "train_kwargs": kwargs,
        "save_dir": str(save_dir) if save_dir else None,
        "status": "completed",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
