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
    surface: str = "unknown"
    # Road extent and the intended central route are different quantities.
    row_bounds: tuple = ()
    route_left: float = 0.36
    route_right: float = 0.64
    forward_support: float = 0.0
    left_support: float = 0.0
    right_support: float = 0.0

    def contains(self, x: float, y: float) -> bool:
        if not self.route_left <= x <= self.route_right or y < self.floor_y:
            return False
        if not self.row_bounds:
            return self.left <= x <= self.right
        _, left, right = min(self.row_bounds, key=lambda row: abs(row[0] - y))
        if left <= x <= right:
            return True
        # A close vehicle/person can occlude the road mask all the way to the
        # bottom edge. Never turn that occlusion into a safe classification:
        # retain the central route for contact points in the lowest 15% and let
        # the temporal risk layer decide whether to warn.
        return y >= 0.85


class SegformerWalkableRegionEstimator:
    """SegFormer ADE20K road/sidewalk estimate with a safe fallback.

    Model weights are downloaded to the user's Transformers cache and are not
    committed to the repository.  ``estimate`` accepts an OpenCV BGR frame.
    """

    DEFAULT_MODEL = "nvidia/segformer-b0-finetuned-ade-512-512"
    FALLBACK = WalkableRegionEstimate(
        0.36, 0.64, 0.48, 0.25, "geometry_fallback", "unknown"
    )

    def __init__(self, model_name: str = DEFAULT_MODEL, device: Optional[str] = None,
                 min_confidence: float = 0.15):
        self.model_name = model_name
        self.min_confidence = float(min_confidence)
        self._processor = None
        self._model = None
        self._device = device
        self.load_error = None
        self.inference_error = None

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
        except Exception as exc:
            self.inference_error = f"{type(exc).__name__}: {exc}"
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
    def corridor_support(cls, component, probabilities, top_left, top_right,
                         bottom_left=None, bottom_right=None):
        """Minimum row support of a corridor connected to the user's feet.

        Keep holes and unknown pixels. A min/max outline of a mask would fill
        obstacle holes and is only useful for drawing, never for steering.
        This image-space evidence does not establish a metric clearance.
        """
        import numpy as np
        height, width = component.shape
        bottom_left = top_left if bottom_left is None else bottom_left
        bottom_right = top_right if bottom_right is None else bottom_right
        support = []
        for row in range(int(height * 0.60), max(int(height * 0.60) + 1, int(height * 0.98))):
            y = row / height
            progress = (y - 0.60) / 0.38
            left = top_left + (bottom_left - top_left) * progress
            right = top_right + (bottom_right - top_right) * progress
            x1, x2 = int(left * width), max(int(left * width) + 1, int(right * width))
            band = component[row, x1:x2] & (probabilities[row, x1:x2] >= 0.65)
            support.append(float(np.mean(band)) if band.size else 0.0)
        return min(support, default=0.0)

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
            if box is None or len(box) != 4 or not np.all(np.isfinite(box)):
                continue
            if box[2] <= box[0] or box[3] <= box[1]:
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
        # A lower-image percentile delayed detection of a vehicle already on
        # the road. Use the near horizon instead, then check local row bounds.
        floor_y = float(np.percentile(ys, 2) / height)
        coverage = min(1.0, len(xs) / float(width * height * 0.35))
        confidence = max(0.15, min(0.95, 0.35 + 0.6 * coverage))
        if right - left < 0.16:
            return cls.FALLBACK
        component_labels = labels[component]
        if np.all(component_labels == 6):
            surface = "road"
        elif np.all(component_labels == 11):
            surface = "sidewalk"
        elif np.all(np.isin(component_labels, (3, 52))):
            surface = "floor_or_path"
        else:
            surface = "mixed_walkable"
        rows = []
        for fraction in np.linspace(floor_y, 0.98, 16):
            row_y = int(fraction * height)
            band = component[max(0, row_y - 2):min(height, row_y + 3)]
            _, band_x = np.where(band)
            if len(band_x) >= 5:
                rows.append((float(fraction), float(np.percentile(band_x, 2) / width),
                             float(np.percentile(band_x, 98) / width)))
        return WalkableRegionEstimate(
            left, right, floor_y, confidence, "segformer_ade20k", surface, tuple(rows),
            forward_support=cls.corridor_support(component, probabilities, 0.36, 0.64, 0.40, 0.60),
            left_support=cls.corridor_support(component, probabilities, 0.15, 0.35, 0.15, 0.35),
            right_support=cls.corridor_support(component, probabilities, 0.65, 0.85, 0.65, 0.85),
        )


class TemporalWalkableRegionFilter:
    """Reject abrupt learned-mask jumps instead of authorizing a new route.

    Segmentation is sampled sparsely on the 4060. A single mask can jump from
    road to sky or parking-row pixels when the camera moves or a target
    occludes the bottom seed. The safe response is a geometry fallback, which
    keeps obstacle checks conservative and prevents direction guidance from
    using the unstable mask as positive evidence.
    """

    def __init__(self, max_floor_delta=0.12, max_boundary_delta=0.22):
        if max_floor_delta <= 0 or max_boundary_delta <= 0:
            raise ValueError("temporal region thresholds must be positive")
        self.max_floor_delta = float(max_floor_delta)
        self.max_boundary_delta = float(max_boundary_delta)
        self.previous = None

    def update(self, region):
        if region.source == "geometry_fallback":
            self.previous = None
            return region
        previous = self.previous
        self.previous = region
        if previous is None or previous.source == "geometry_fallback":
            return region
        if (abs(region.floor_y - previous.floor_y) > self.max_floor_delta or
                abs(region.left - previous.left) > self.max_boundary_delta or
                abs(region.right - previous.right) > self.max_boundary_delta):
            return WalkableRegionEstimate(
                0.36, 0.64, 0.48, 0.25, "geometry_fallback", "unknown",
                route_left=region.route_left, route_right=region.route_right,
            )
        return region
