"""独立于 Ultralytics 的 YOLOv8 ONNX 预处理、解码和 NMS 参考实现。"""

from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
    "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard",
    "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]


def letterbox(image, size=640, color=114):
    """返回 NCHW RGB float32 张量、缩放比例和 (x_pad, y_pad)。"""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image 必须是 HWC 三通道图像")
    height, width = image.shape[:2]
    if height <= 0 or width <= 0:
        raise ValueError("image 尺寸必须为正")
    ratio = min(size / width, size / height)
    resized_width = int(round(width * ratio))
    resized_height = int(round(height * ratio))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    pad_x = (size - resized_width) / 2.0
    pad_y = (size - resized_height) / 2.0
    canvas = np.full((size, size, 3), color, dtype=np.uint8)
    left = int(round(pad_x - 0.1))
    top = int(round(pad_y - 0.1))
    canvas[top : top + resized_height, left : left + resized_width] = resized
    tensor = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return tensor[None, ...], ratio, (pad_x, pad_y)


def _iou(one, many):
    x1 = np.maximum(one[0], many[:, 0])
    y1 = np.maximum(one[1], many[:, 1])
    x2 = np.minimum(one[2], many[:, 2])
    y2 = np.minimum(one[3], many[:, 3])
    intersection = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    area_one = max(0.0, one[2] - one[0]) * max(0.0, one[3] - one[1])
    area_many = np.maximum(0.0, many[:, 2] - many[:, 0]) * np.maximum(0.0, many[:, 3] - many[:, 1])
    return intersection / np.maximum(area_one + area_many - intersection, 1e-9)


def _nms(boxes, scores, class_ids, iou_threshold):
    keep = []
    for class_id in np.unique(class_ids):
        indices = np.where(class_ids == class_id)[0]
        order = indices[np.argsort(scores[indices])[::-1]]
        while len(order):
            current = order[0]
            keep.append(int(current))
            if len(order) == 1:
                break
            overlaps = _iou(boxes[current], boxes[order[1:]])
            order = order[1:][overlaps <= iou_threshold]
    return keep


def decode_yolov8(output, original_shape, ratio, pad, conf_threshold=0.25, iou_threshold=0.7):
    """将 YOLOv8 的 [1,84,8400] 输出转为原图像素坐标。"""
    raw = np.asarray(output)
    if raw.ndim == 3:
        raw = raw[0]
    if raw.ndim != 2:
        raise ValueError("ONNX 输出必须是二维或三维张量")
    if (raw.shape[1] < 5 and raw.shape[0] >= 5) or (
        raw.shape[0] <= 128 and raw.shape[1] > raw.shape[0]
    ):
        raw = raw.T
    if raw.shape[1] < 5:
        raise ValueError("ONNX 输出通道数不足")
    boxes_xywh = raw[:, :4]
    class_scores = raw[:, 4:]
    class_ids = np.argmax(class_scores, axis=1)
    scores = class_scores[np.arange(len(class_scores)), class_ids]
    selected = scores >= conf_threshold
    if not np.any(selected):
        return []
    boxes_xywh = boxes_xywh[selected]
    scores = scores[selected]
    class_ids = class_ids[selected]
    cx, cy, width, height = boxes_xywh.T
    boxes = np.column_stack((cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2))
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad[0]) / ratio
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad[1]) / ratio
    image_height, image_width = original_shape[:2]
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, image_width)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, image_height)
    keep = _nms(boxes, scores, class_ids, iou_threshold)
    detections = []
    for index in keep:
        class_id = int(class_ids[index])
        detections.append(
            {
                "class_id": class_id,
                "class_name": COCO_NAMES[class_id] if class_id < len(COCO_NAMES) else str(class_id),
                "confidence": round(float(scores[index]), 6),
                "box": [round(float(value), 3) for value in boxes[index]],
            }
        )
    return detections


def infer_image(image, model_path, conf_threshold=0.25, iou_threshold=0.7, providers=None):
    """运行一次 ONNX 推理并返回检测列表；Android 可据此移植输入/输出契约。"""
    tensor, ratio, pad = letterbox(image)
    session = ort.InferenceSession(str(Path(model_path)), providers=providers or ["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: tensor})[0]
    return decode_yolov8(output, image.shape, ratio, pad, conf_threshold, iou_threshold)
