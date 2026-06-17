import math
from typing import Any, Dict, Tuple


def _xy(point: Dict[str, Any]) -> Tuple[float, float]:
    return float(point["x"]), float(point["y"])


def compute_px_to_mm(
    point_a: Dict[str, Any],
    point_b: Dict[str, Any],
    real_distance_mm: float,
) -> Dict[str, float]:
    """Return calibration scale from two image points and a known real distance."""
    if real_distance_mm <= 0:
        raise ValueError("real_distance_mm must be greater than zero")

    ax, ay = _xy(point_a)
    bx, by = _xy(point_b)
    pixel_distance = math.hypot(ax - bx, ay - by)
    if pixel_distance == 0:
        raise ValueError("calibration points must not be identical")

    px_to_mm = real_distance_mm / pixel_distance
    return {
        "pixel_distance": round(pixel_distance, 4),
        "real_distance_mm": round(float(real_distance_mm), 4),
        "px_to_mm": round(px_to_mm, 8),
        "mm_to_px": round(1.0 / px_to_mm, 8),
    }
