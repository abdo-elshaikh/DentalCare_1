"""Measurements engine

Provides robust cephalometric measurement computations with optional
uncertainty estimation using Monte-Carlo perturbation of landmark positions.

Key functions:
- `compute_measurements`: deterministic measurements (delegates to analysis.compute_cephalometric_measurements)
- `compute_measurements_with_uncertainty`: Monte-Carlo sampling to estimate measurement SDs
- `summary_report`: combines measurements with norms to produce z-scores and classifications

This module builds on `api.analysis` and `api.norms` to remain protocol-aware.
"""
from __future__ import annotations

import random
import math
from typing import Any, Dict, List, Optional, Tuple

from .analysis import compute_cephalometric_measurements
from .norms import get_norm_tuple


def compute_measurements(
    landmarks: List[Dict[str, Any]], px_to_mm: float = 1.0
) -> Dict[str, float]:
    """Deterministic measurements from landmarks.

    Returns a dict mapping measurement name -> value (angles in degrees, distances in mm).
    """
    return compute_cephalometric_measurements(landmarks, px_to_mm)


def _perturb_landmarks(landmarks: List[Dict[str, Any]], base_sigma_px: float = 2.0) -> List[Dict[str, Any]]:
    """Return a new landmark list with Gaussian perturbation applied.

    Per-landmark sigma is scaled by (1 - score).
    Uses anisotropic perturbation for specific landmarks (e.g., Menton is less certain vertically).
    """
    out = []
    
    # Define anisotropic multipliers for specific landmarks (id: (x_scale, y_scale))
    # E.g., Menton (8) is usually clearer horizontally than vertically (due to symphysis curvature).
    # Gonion (10) might be clearer vertically than horizontally.
    anisotropic_factors = {
        8: (0.5, 1.5),  # Menton: tighter X, looser Y
        10: (1.5, 0.8), # Gonion: looser X, tighter Y
        9: (1.2, 1.2),  # Gnathion: generally harder to pinpoint
    }

    for lm in landmarks:
        s = lm.get("score", None)
        try:
            s = float(s) if s is not None else None
        except Exception:
            s = None
            
        if s is None:
            sigma = base_sigma_px
        else:
            if s > 1.5:
                s = min(1.0, max(0.0, s / 255.0))
            else:
                s = max(0.0, min(1.0, s))
            sigma = base_sigma_px * (1.0 - s)
            
        lm_id = int(lm.get("id", -1))
        scale_x, scale_y = anisotropic_factors.get(lm_id, (1.0, 1.0))
        
        dx = random.gauss(0.0, sigma * scale_x)
        dy = random.gauss(0.0, sigma * scale_y)
        
        new = dict(lm)
        new["x"] = float(new.get("x", 0.0)) + dx
        new["y"] = float(new.get("y", 0.0)) + dy
        out.append(new)
    return out


def compute_measurements_with_uncertainty(
    landmarks: List[Dict[str, Any]],
    px_to_mm: float = 1.0,
    samples: int = 200,
    base_sigma_px: float = 2.0,
) -> Dict[str, Dict[str, float]]:
    """Estimate measurement mean and SD via Monte-Carlo.

    Returns a mapping measurement -> {"value": nominal_value, "mean": mean, "sd": sd}.
    For angular measures the units are degrees; for linear measures they are millimetres.
    """
    nominal = compute_measurements(landmarks, px_to_mm)
    if not samples or samples <= 1:
        return {k: {"value": v, "mean": v, "sd": 0.0} for k, v in nominal.items()}

    # accumulate samples
    acc: Dict[str, List[float]] = {k: [] for k in nominal.keys()}
    for _ in range(samples):
        pert = _perturb_landmarks(landmarks, base_sigma_px=base_sigma_px)
        vals = compute_measurements(pert, px_to_mm)
        for k in nominal.keys():
            acc[k].append(vals.get(k, float("nan")))

    results: Dict[str, Dict[str, float]] = {}
    for k, v in nominal.items():
        samp = [x for x in acc.get(k, []) if not math.isnan(x)]
        if not samp:
            mean = v
            sd = 0.0
        else:
            mean = float(sum(samp) / len(samp))
            var = sum((x - mean) ** 2 for x in samp) / max(1, len(samp) - 1)
            sd = math.sqrt(var)
        results[k] = {"value": v, "mean": round(mean, 3), "sd": round(sd, 3)}
    return results


def summary_report(
    landmarks: List[Dict[str, Any]],
    px_to_mm: float = 1.0,
    samples: int = 200,
    base_sigma_px: float = 2.0,
    ethnic_profile: str = "Caucasian",
    protocol_id: str = "core_lateral",
) -> Dict[str, Any]:
    """Produce a clinician-ready summary including uncertainty and z-scores.

    Output structure:
    {
      "measurements": [ {measurement, value, mean, sd, norm_mean, norm_sd, z_score, status, unit}, ... ],
      "landmark_count": N,
      "px_to_mm": px_to_mm,
    }
    """
    mc = compute_measurements_with_uncertainty(landmarks, px_to_mm, samples=samples, base_sigma_px=base_sigma_px)
    rows = []
    for name, stats in mc.items():
        value = stats.get("value")
        mean = stats.get("mean")
        sd = stats.get("sd")
        norm_mean, norm_sd, meta = get_norm_tuple(protocol_id, name, ethnic_profile)
        # compute z-score using combined uncertainty (measurement sd + normative sd)
        combined_sd = math.sqrt((sd or 0.0) ** 2 + (norm_sd or 0.0) ** 2)
        z = abs((mean - norm_mean) / (combined_sd or 1.0))
        status = "normal" if z <= 1.0 else "mild" if z <= 2.0 else "severe"
        rows.append(
            {
                "measurement": name,
                "value": round(value, 3),
                "mean": mean,
                "sd": sd,
                "norm_mean": norm_mean,
                "norm_sd": norm_sd,
                "z_score": round(z, 3),
                "status": status,
            }
        )

    return {
        "measurements": rows,
        "landmark_count": len(landmarks),
        "px_to_mm": px_to_mm,
    }
