"""Validation for lateral cephalometric X-ray uploads."""

from io import BytesIO
from pathlib import Path
from typing import Union

import numpy as np
import torch
from PIL import Image, UnidentifiedImageError
from torchvision import transforms

from .model import run_inference
from .utils import postprocess_landmarks, preprocess_image


CLASS_NAMES = ("lateral_ceph", "other_xray", "non_xray")
SUPPORTED_FORMATS = {"JPEG", "PNG", "BMP", "TIFF"}
MAX_IMAGE_PIXELS = 40_000_000 


class XrayValidator:
    """Run a three-class TorchScript classifier and enforce an accept threshold."""

    def __init__(
        self,
        model_path: Union[str, Path],
        threshold: float = 0.90,
    ) -> None:
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

        self.model = torch.jit.load(str(model_path), map_location="cpu")
        self.model.eval()
        self.threshold = threshold
        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )

    def validate(self, image_bytes: bytes) -> dict:
        try:
            with Image.open(BytesIO(image_bytes)) as source:
                detected_format = source.format
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    return self._rejected(
                        "invalid_image",
                        0.0,
                        "Image dimensions are too large.",
                    )
                if source.width < 256 or source.height < 256:
                    return self._rejected(
                        "invalid_image",
                        0.0,
                        "Image resolution is too low; both dimensions must be at least 256 pixels.",
                    )
                source.load()
                image = source.convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError):
            return self._rejected(
                "invalid_image",
                0.0,
                "The uploaded file is not a valid image.",
            )

        if detected_format not in SUPPORTED_FORMATS:
            return self._rejected(
                "unsupported_image",
                0.0,
                "Please upload a JPEG, PNG, BMP, or TIFF image.",
            )

        tensor = self.transform(image).unsqueeze(0)
        with torch.inference_mode():
            logits = self.model(tensor)
            if isinstance(logits, (tuple, list)):
                logits = logits[0]
            probabilities = torch.softmax(logits, dim=1)[0]

        if probabilities.numel() != len(CLASS_NAMES):
            raise ValueError(
                f"X-ray classifier returned {probabilities.numel()} classes; "
                f"expected {len(CLASS_NAMES)}."
            )

        index = int(probabilities.argmax().item())
        label = CLASS_NAMES[index]
        confidence = float(probabilities[index].item())
        accepted = label == "lateral_ceph" and confidence >= self.threshold

        return {
            "accepted": accepted,
            "label": label,
            "confidence": round(confidence, 4),
            "reason": None
            if accepted
            else "Only lateral cephalometric X-ray images are accepted.",
        }

    @staticmethod
    def _rejected(label: str, confidence: float, reason: str) -> dict:
        return {
            "accepted": False,
            "label": label,
            "confidence": confidence,
            "reason": reason,
        }


class LandmarkXrayValidator:
    """Fallback validator using the installed cephalometric landmark model.

    This is intentionally stricter than ordinary image validation. A dedicated
    three-class classifier remains preferred when ``xray_validator.pt`` exists.
    """

    def __init__(
        self,
        landmark_model,
        min_mean_score: float = 3.0,
        min_landmark_score: float = 1.5,
        max_colored_pixel_ratio: float = 0.10,
    ) -> None:
        self.model = landmark_model
        self.min_mean_score = min_mean_score
        self.min_landmark_score = min_landmark_score
        self.max_colored_pixel_ratio = max_colored_pixel_ratio

    def validate(self, image_bytes: bytes) -> dict:
        try:
            with Image.open(BytesIO(image_bytes)) as source:
                detected_format = source.format
                width, height = source.size
                if width * height > MAX_IMAGE_PIXELS:
                    return XrayValidator._rejected(
                        "invalid_image", 0.0, "Image dimensions are too large."
                    )
                if width < 256 or height < 256:
                    return XrayValidator._rejected(
                        "invalid_image",
                        0.0,
                        "Image resolution is too low; both dimensions must be at least 256 pixels.",
                    )
                source.load()
                image = np.asarray(source.convert("RGB"), dtype=np.int16)
        except (UnidentifiedImageError, OSError, ValueError):
            return XrayValidator._rejected(
                "invalid_image", 0.0, "The uploaded file is not a valid image."
            )

        if detected_format not in SUPPORTED_FORMATS:
            return XrayValidator._rejected(
                "unsupported_image",
                0.0,
                "Please upload a JPEG, PNG, BMP, or TIFF image.",
            )

        channel_delta = image.max(axis=2) - image.min(axis=2)
        colored_pixel_ratio = float(np.mean(channel_delta > 12))
        if colored_pixel_ratio > self.max_colored_pixel_ratio:
            return XrayValidator._rejected(
                "non_xray",
                round(1.0 - colored_pixel_ratio, 4),
                "The image appears to be a photograph or color image, not a raw X-ray.",
            )

        tensor, original_size = preprocess_image(image_bytes)
        heatmaps, offsets = run_inference(self.model, tensor)
        landmarks = postprocess_landmarks(heatmaps, original_size, offsets=offsets)
        scores = np.asarray([point["score"] for point in landmarks], dtype=np.float32)
        normalized_x = np.asarray([point["x"] for point in landmarks]) / width
        normalized_y = np.asarray([point["y"] for point in landmarks]) / height

        mean_score = float(scores.mean())
        minimum_score = float(scores.min())
        x_span = float(normalized_x.max() - normalized_x.min())
        y_span = float(normalized_y.max() - normalized_y.min())
        plausible_geometry = 0.25 <= x_span <= 0.85 and 0.25 <= y_span <= 0.85
        accepted = (
            mean_score >= self.min_mean_score
            and minimum_score >= self.min_landmark_score
            and plausible_geometry
        )

        confidence = min(
            0.99,
            mean_score / self.min_mean_score * 0.75
            if accepted
            else mean_score / self.min_mean_score * 0.5,
        )
        return {
            "accepted": accepted,
            "label": "lateral_ceph" if accepted else "non_xray",
            "confidence": round(max(0.0, confidence), 4),
            "reason": None
            if accepted
            else "The image does not contain a plausible lateral cephalometric X-ray.",
            "validation_mode": "landmark_fallback",
        }
