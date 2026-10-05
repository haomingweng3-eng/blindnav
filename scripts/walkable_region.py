"""Optional learned walkable-region adapter for desktop/4060 validation.

The phone contract stays independent of this module.  When the SegFormer
weights are unavailable, callers receive the conservative geometry fallback;
the adapter never turns an unknown mask into a safe route.
"""

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class WalkableRegionEstimate:
    left: float
    right: float
    floor_y: float
    confidence: float
    source: str

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and y >= self.floor_y


class SegformerWalkableRegionEstimator:
    """SegFormer ADE20K road/sidewalk estimate with a safe fallback.

    Model weights are downloaded to the user's Transformers cache and are not
    committed to the repository.  ``estimate`` accepts an OpenCV BGR frame.
    """

    DEFAULT_MODEL = "nvidia/segformer-b0-finetuned-ade-512-512"
    FALLBACK = WalkableRegionEstimate(
        0.32, 0.68, 0.48, 0.25, "geometry_fallback"
    )

    def __init__(self, model_name: str = DEFAULT_MODEL, device: Optional[str] = None,
                 min_confidence: float = 0.15):
        self.model_name = model_name
        self.min_confidence = float(min_confidence)
        self._processor = None
        self._model = None
        self._device = device
        self.load_error = None

    @property
    def available(self) -> bool:
        return self._model is not None and self._processor is not None

    def load(self):
        if self.available or self.load_error:
            return self.available
        try:
            import torch
            from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation

            self._processor = SegformerImageProcessor.from_pretrained(self.model_name)
            self._model = SegformerForSemanticSegmentation.from_pretrained(self.model_name)
            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model.to(self._device)
            self._model.eval()
            return True
        except Exception as exc:  # optional dependency/weights must not break detection
            self.load_error = f"{type(exc).__name__}: {exc}"
            self._processor = None
            self._model = None
            return False

    def estimate(self, frame, detections: Iterable[dict] = ()) -> WalkableRegionEstimate:
        if frame is None or not self.load():
            return self.FALLBACK
        try:
            import numpy as np
            import torch
            height, width = frame.shape[:2]
            # OpenCV BGR -> RGB; copy removes the negative stride that the
            # Transformers image processor cannot pass to torch.
            rgb = frame[:, :, ::-1].copy()
            inputs = self._processor(images=rgb, return_tensors="pt")
            inputs = {key: value.to(self._device) for key, value in inputs.items()}
            with torch.no_grad():
                logits = self._model(**inputs).logits
            logits = torch.nn.functional.interpolate(
                logits, size=(height, width), mode="bilinear", align_corners=False
            )[0]
            labels = logits.argmax(dim=0).detach().cpu().numpy()
            probabilities = logits.softmax(dim=0).max(dim=0).values.detach().cpu().numpy()
            return self.mask_to_region(labels, probabilities, self._walkable_ids(), detections)
        except Exception:
            return self.FALLBACK

    def _walkable_ids(self):
        config = getattr(self._model, "config", None)
        id2label = getattr(config, "id2label", {}) or {}
        ids = set()
        for raw_id, raw_name in id2label.items():
            name = str(raw_name).lower().replace("_", " ")
            if any(token in name for token in ("road", "sidewalk", "path", "floor", "pavement")):
                ids.add(int(raw_id))
        return ids

    @classmethod
    def mask_to_region(cls, labels, probabilities, walkable_ids, detections=()):
        """Convert a semantic mask into a conservative normalized corridor.

        The component is seeded near the bottom centre, so a road/sidewalk
        elsewhere in the image cannot silently become the walking route.
        """
        import numpy as np
        import cv2

        labels = np.asarray(labels)
        probabilities = np.asarray(probabilities)
        if labels.ndim != 2 or probabilities.shape != labels.shape or not walkable_ids:
            return cls.FALLBACK
        mask = np.isin(labels, list(walkable_ids)) & (probabilities >= 0.35)
        height, width = mask.shape
        if width < 2 or height < 2:
            return cls.FALLBACK
        for detection in detections or ():
            box = detection.get("box") if isinstance(detection, dict) else None
            if not box or len(box) != 4:
                continue
            x1, y1, x2, y2 = [int(max(0, value)) for value in box]
            mask[min(height, y1):min(height, y2 + 1), min(width, x1):min(width, x2 + 1)] = False

        # Start from several bottom-centre seeds to tolerate a small person or
        # vehicle mask at exactly the image centre.
        seeds = [(height - 1, int(width * fraction)) for fraction in (0.45, 0.50, 0.55)]
        seed = next((point for point in seeds if mask[point]), None)
        if seed is None:
            return cls.FALLBACK
        count, components = cv2.connectedComponents(mask.astype("uint8"), connectivity=8)
        component_id = int(components[seed])
        if component_id == 0:
            return cls.FALLBACK
        component = components == component_id
        ys, xs = np.where(component)
        if len(xs) < max(20, int(width * height * 0.01)):
            return cls.FALLBACK
        lower = ys >= int(height * 0.55)
        lower_xs = xs[lower]
        if len(lower_xs) < 10:
            lower_xs = xs
        left = float(np.percentile(lower_xs, 5) / width)
        right = float(np.percentile(lower_xs, 95) / width)
        floor_y = float(np.percentile(ys, 35) / height)
        coverage = min(1.0, len(xs) / float(width * height * 0.35))
        confidence = max(0.15, min(0.95, 0.35 + 0.6 * coverage))
        if right - left < 0.16:
            return cls.FALLBACK
        return WalkableRegionEstimate(left, right, floor_y, confidence, "segformer_ade20k")
