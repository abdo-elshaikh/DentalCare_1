import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from shared.landmarks import LANDMARK_NAMES, LANDMARK_SHORTS

from .norms import get_measurement_norm, get_norm_tuple

# Legacy ethnic fallbacks when a protocol norm is missing from reference files.
ETHNIC_NORMS = {
    "Caucasian": {
        "SNA": (81.0, 5.0),
        "SNB": (78.0, 5.0),
        "ANB": (3.0, 2.0),
        "FMA (FH-MP)": (27.0, 5.0),
        "Facial Angle (N-S-Gn)": (67.0, 3.0),
        "SN-GoGn": (32.0, 5.0),
        "IMPA": (90.0, 5.0),
        "FMIA": (65.0, 5.0),
        "Interincisal angle": (130.0, 8.0),
        "Lower anterior facial height": (70.0, 3.0),
        "Nasolabial angle": (102.0, 8.0),
            "Articular angle (S-Ar-Go)": (143.0, 6.0),
            "Gonial angle (Ar-Go-Me)": (130.0, 7.0),
            "Posterior face height / Anterior face height (S-Go / N-Me) ratio": (0.62, 0.05),
            "Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me)": (396.0, 5.0),
    },
    "East Asian": {
        "SNA": (82.5, 3.0),
        "SNB": (79.0, 3.0),
        "ANB": (3.5, 1.5),
        "FMA (FH-MP)": (29.5, 4.0),
        "Facial Angle (N-S-Gn)": (65.0, 2.5),
        "SN-GoGn": (34.0, 4.0),
        "IMPA": (92.0, 5.0),
        "FMIA": (63.0, 5.0),
        "Interincisal angle": (132.0, 6.0),
        "Lower anterior facial height": (68.0, 3.0),
        "Nasolabial angle": (100.0, 8.0),
            "Articular angle (S-Ar-Go)": (143.0, 6.0),
            "Gonial angle (Ar-Go-Me)": (130.0, 7.0),
            "Posterior face height / Anterior face height (S-Go / N-Me) ratio": (0.62, 0.05),
            "Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me)": (396.0, 5.0),
    },
    "Middle Eastern": {
        "SNA": (81.5, 4.0),
        "SNB": (78.5, 4.0),
        "ANB": (3.0, 2.0),
        "FMA (FH-MP)": (28.0, 4.5),
        "Facial Angle (N-S-Gn)": (66.5, 3.0),
        "SN-GoGn": (33.0, 4.5),
        "IMPA": (91.0, 5.0),
        "FMIA": (64.0, 5.0),
        "Interincisal angle": (131.0, 7.0),
        "Lower anterior facial height": (69.0, 3.0),
        "Nasolabial angle": (101.0, 8.0),
            "Articular angle (S-Ar-Go)": (143.0, 6.0),
            "Gonial angle (Ar-Go-Me)": (130.0, 7.0),
            "Posterior face height / Anterior face height (S-Go / N-Me) ratio": (0.62, 0.05),
            "Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me)": (396.0, 5.0),
    },
}

MEASUREMENT_GROUPS = {
    "SNA": "Skeletal",
    "SNB": "Skeletal",
    "ANB": "Skeletal",
    "FMA (FH-MP)": "Vertical",
    "Facial Angle (N-S-Gn)": "Vertical Pattern",
    "SN-GoGn": "Vertical",
    "IMPA": "Dental",
    "FMIA": "Dental",
    "Interincisal angle": "Dental",
    "Lower anterior facial height": "Vertical",
    "Nasolabial angle": "Soft Tissue",
    "Articular angle (S-Ar-Go)": "Skeletal Pattern",
    "Gonial angle (Ar-Go-Me)": "Skeletal Pattern",
    "Posterior face height / Anterior face height (S-Go / N-Me) ratio": "Vertical",
    "Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me)": "Skeletal Pattern",
}

MEASUREMENT_UNITS = {
    "SNA": "deg",
    "SNB": "deg",
    "ANB": "deg",
    "FMA (FH-MP)": "deg",
    "Facial Angle (N-S-Gn)": "deg",
    "SN-GoGn": "deg",
    "IMPA": "deg",
    "FMIA": "deg",
    "Interincisal angle": "deg",
    "Lower anterior facial height": "mm",
    "Nasolabial angle": "deg",
    "Articular angle (S-Ar-Go)": "deg",
    "Gonial angle (Ar-Go-Me)": "deg",
    "Posterior face height / Anterior face height (S-Go / N-Me) ratio": "ratio",
    "Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me)": "deg",
}


def _point(landmark: Dict[str, Any]) -> Tuple[float, float]:
    return float(landmark["x"]), float(landmark["y"])


def compute_distance(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    x1, y1 = _point(p1)
    x2, y2 = _point(p2)
    return math.hypot(x1 - x2, y1 - y2)


def compute_angle(
    p_a: Dict[str, Any],
    p_b: Dict[str, Any],
    p_c: Dict[str, Any],
    signed: bool = False
) -> Optional[float]:
    ax, ay = _point(p_a)
    bx, by = _point(p_b)
    cx, cy = _point(p_c)
    
    # Check if points are identical to the vertex
    if (ax == bx and ay == by) or (cx == bx and cy == by):
        return None
        
    a_ang = math.degrees(math.atan2(ay - by, ax - bx))
    c_ang = math.degrees(math.atan2(cy - by, cx - bx))
    
    diff = a_ang - c_ang
    
    # Normalize to [-180, 180]
    while diff <= -180.0: diff += 360.0
    while diff > 180.0: diff -= 360.0
    
    if not signed:
        return abs(diff)
    return diff


def compute_line_angle(
    p1: Dict[str, Any],
    p2: Dict[str, Any],
    p3: Dict[str, Any],
    p4: Dict[str, Any],
) -> Optional[float]:
    x1, y1 = _point(p1)
    x2, y2 = _point(p2)
    x3, y3 = _point(p3)
    x4, y4 = _point(p4)
    if (x1, y1) == (x2, y2) or (x3, y3) == (x4, y4):
        return None
    a1 = math.degrees(math.atan2(y2 - y1, x2 - x1))
    a2 = math.degrees(math.atan2(y4 - y3, x4 - x3))
    diff = abs(a1 - a2) % 360
    if diff > 180:
        diff = 360 - diff
    return diff


def distance_point_to_line(p: Dict[str, Any], l1: Dict[str, Any], l2: Dict[str, Any]) -> float:
    px, py = _point(p)
    x1, y1 = _point(l1)
    x2, y2 = _point(l2)
    num = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1)
    den = math.hypot(y2 - y1, x2 - x1)
    return num / den if den != 0 else 0.0


def _landmark_map(landmarks: Iterable[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return {int(lm["id"]): lm for lm in landmarks if "id" in lm}


def compute_cephalometric_measurements(
    landmarks: List[Dict[str, Any]],
    px_to_mm: float = 1.0,
) -> Dict[str, float]:
    """Compute lateral cephalometric measurements from the 19-point protocol."""
    lm = _landmark_map(landmarks)
    results: Dict[str, float] = {}

    if all(k in lm for k in (1, 2, 5)):
        angle = compute_angle(lm[1], lm[2], lm[5])
        if angle is not None:
            results["SNA"] = angle

    if all(k in lm for k in (1, 2, 6)):
        angle = compute_angle(lm[1], lm[2], lm[6])
        if angle is not None:
            results["SNB"] = angle

    if "SNA" in results and "SNB" in results:
        results["ANB"] = results["SNA"] - results["SNB"]

    if all(k in lm for k in (1, 2, 9)):
        angle = compute_angle(lm[1], lm[2], lm[9])
        if angle is not None:
            results["Facial Angle (N-S-Gn)"] = angle

    if all(k in lm for k in (4, 3, 10, 8)):
        angle = compute_line_angle(lm[4], lm[3], lm[10], lm[8])
        if angle is not None:
            results["FMA (FH-MP)"] = angle

    if all(k in lm for k in (4, 3, 2, 7)):
        angle = compute_line_angle(lm[4], lm[3], lm[2], lm[7])
        if angle is not None:
            results["Facial angle (FH-Na-Pg) (°)"] = angle

    if all(k in lm for k in (1, 2, 10, 9)):
        angle = compute_line_angle(lm[1], lm[2], lm[10], lm[9])
        if angle is not None:
            results["SN-GoGn"] = angle

    if all(k in lm for k in (6, 11, 10, 8)):
        angle = compute_line_angle(lm[6], lm[11], lm[10], lm[8])
        if angle is not None:
            results["IMPA"] = angle

    if "FMA (FH-MP)" in results and "IMPA" in results:
        results["FMIA"] = round(180.0 - results["FMA (FH-MP)"] - results["IMPA"], 2)

    # Interincisal angle
    if all(k in lm for k in (5, 12, 6, 11)):
        angle = compute_line_angle(lm[5], lm[12], lm[6], lm[11])
        if angle is not None:
            results["Interincisal angle"] = angle

    if all(k in lm for k in (18, 8)):
        results["Lower anterior facial height"] = round(
            compute_distance(lm[18], lm[8]) * px_to_mm, 2
        )

    if all(k in lm for k in (13, 14, 15)):
        angle = compute_angle(lm[13], lm[15], lm[14])
        if angle is not None:
            results["Nasolabial angle"] = angle

    if all(k in lm for k in (1, 10, 8)):
        posterior = compute_distance(lm[1], lm[10])
        if 2 in lm:
            anterior = compute_distance(lm[2], lm[8])
            if anterior != 0:
                results["Posterior face height / Anterior face height (S-Go / N-Me) ratio"] = round(
                    posterior / anterior,
                    2,
                )

    saddle_angle = None
    articular_angle = None
    gonial_angle = None
    if all(k in lm for k in (1, 2, 19)):
        saddle_angle = compute_angle(lm[2], lm[1], lm[19])
    if all(k in lm for k in (1, 19, 10)):
        articular_angle = compute_angle(lm[1], lm[19], lm[10])
        if articular_angle is not None:
            results["Articular angle (S-Ar-Go)"] = round(articular_angle, 2)
    if all(k in lm for k in (19, 10, 8)):
        gonial_angle = compute_angle(lm[19], lm[10], lm[8])
        if gonial_angle is not None:
            results["Gonial angle (Ar-Go-Me)"] = round(gonial_angle, 2)
    if saddle_angle is not None and articular_angle is not None and gonial_angle is not None:
        results["Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me)"] = round(
            saddle_angle + articular_angle + gonial_angle,
            2,
        )

    # Downs / Steiner additions
    if all(k in lm for k in (1, 9, 4, 3)):
        # Y-axis
        angle = compute_line_angle(lm[1], lm[9], lm[4], lm[3])
        if angle is not None:
            results["Y-axis (S-Gn to FH) (°)"] = angle

    if all(k in lm for k in (2, 5, 7)):
        angle = compute_angle(lm[2], lm[5], lm[7])
        if angle is not None:
            results["Angle of convexity (Na-A-Pg) (°)"] = round(180.0 - angle, 2)

    if all(k in lm for k in (5, 6, 2, 7)):
        angle = compute_line_angle(lm[5], lm[6], lm[2], lm[7])
        if angle is not None:
            results["A-B plane angle (AB-Na-Pg) (°)"] = angle

    if all(k in lm for k in (1, 2, 5, 12)):
        angle = compute_line_angle(lm[1], lm[2], lm[5], lm[12])
        if angle is not None:
            results["Upper incisor to SN (°)"] = angle

    if all(k in lm for k in (2, 5, 12)):
        results["U1-NA (mm)"] = round(distance_point_to_line(lm[12], lm[2], lm[5]) * px_to_mm, 2)
        angle = compute_line_angle(lm[5], lm[12], lm[2], lm[5])
        if angle is not None:
            results["U1-NA (°)"] = angle

    if all(k in lm for k in (2, 6, 11)):
        results["L1-NB (mm)"] = round(distance_point_to_line(lm[11], lm[2], lm[6]) * px_to_mm, 2)
        angle = compute_line_angle(lm[6], lm[11], lm[2], lm[6])
        if angle is not None:
            results["L1-NB (°)"] = angle

    if all(k in lm for k in (7, 2, 6)):
        results["Pg-NB (mm)"] = round(distance_point_to_line(lm[7], lm[2], lm[6]) * px_to_mm, 2)

    return {name: round(value, 2) for name, value in results.items()}


def _default_norm(name: str, ethnic_profile: str) -> Tuple[float, float]:
    norms = ETHNIC_NORMS.get(ethnic_profile, ETHNIC_NORMS["Caucasian"])
    return norms.get(name, (80.0, 2.0))


def _interpret_measurement(
    name: str,
    diff: float,
    sd: float,
    clinical: Optional[str],
) -> Tuple[str, str]:
    if name == "SNA":
        if diff > sd:
            return "Maxillary Prognathism", "Assesses anteroposterior maxillary position relative to the cranial base."
        if diff < -sd:
            return "Maxillary Retrognathism", "Assesses anteroposterior maxillary position relative to the cranial base."
        return "Normal Maxilla", "Assesses anteroposterior maxillary position relative to the cranial base."
    if name == "SNB":
        if diff > sd:
            return "Mandibular Prognathism", "Assesses anteroposterior mandibular position relative to the cranial base."
        if diff < -sd:
            return "Mandibular Retrognathism", "Assesses anteroposterior mandibular position relative to the cranial base."
        return "Normal Mandible", "Assesses anteroposterior mandibular position relative to the cranial base."
    if name == "ANB":
        if diff > sd:
            return "Skeletal Class II", "Summarizes sagittal maxilla-mandible relationship."
        if diff < -sd:
            return "Skeletal Class III", "Summarizes sagittal maxilla-mandible relationship."
        return "Skeletal Class I", "Summarizes sagittal maxilla-mandible relationship."
    if name in ("FMA (FH-MP)", "SN-GoGn"):
        if diff > sd:
            return "Hyperdivergent", "Assesses vertical skeletal pattern."
        if diff < -sd:
            return "Hypodivergent", "Assesses vertical skeletal pattern."
        return "Normodivergent", "Assesses vertical skeletal pattern."
    if name == "IMPA":
        if diff > sd:
            return "Proclined Lower Incisors", "Lower incisor inclination relative to mandibular plane."
        if diff < -sd:
            return "Retroclined Lower Incisors", "Lower incisor inclination relative to mandibular plane."
        return "Normal Lower Incisors", "Lower incisor inclination relative to mandibular plane."
    if name == "FMIA":
        if diff > sd:
            return "Upright Lower Incisors", "Frankfort-mandibular incisor angle (Tweed)."
        if diff < -sd:
            return "Procumbent Lower Incisors", "Frankfort-mandibular incisor angle (Tweed)."
        return "Normal FMIA", "Frankfort-mandibular incisor angle (Tweed)."
    if name == "Interincisal angle":
        if diff > sd:
            return "Increased Overjet Tendency", "Angle between upper and lower incisor axes."
        if diff < -sd:
            return "Deep Bite Tendency", "Angle between upper and lower incisor axes."
        return "Balanced Incisors", "Angle between upper and lower incisor axes."
    if name == "Facial Angle (N-S-Gn)":
        if diff > sd:
            return "High Facial Axis", "Approximates vertical facial axis using S-N-Gn."
        if diff < -sd:
            return "Low Facial Axis", "Approximates vertical facial axis using S-N-Gn."
        return "Balanced Facial Axis", "Approximates vertical facial axis using S-N-Gn."
    if name == "Lower anterior facial height":
        if diff > sd:
            return "Increased Lower Face Height", "ANS to menton distance."
        if diff < -sd:
            return "Decreased Lower Face Height", "ANS to menton distance."
        return "Normal Lower Face Height", "ANS to menton distance."
    if name == "Nasolabial angle":
        if diff > sd:
            return "Obtuse Nasolabial Angle", "Soft-tissue convexity at subnasale."
        if diff < -sd:
            return "Acute Nasolabial Angle", "Soft-tissue convexity at subnasale."
        return "Normal Nasolabial Angle", "Soft-tissue convexity at subnasale."

    label, interpretation = "Within expected range.", "Within expected range."
    if clinical and (diff > sd or diff < -sd):
        interpretation = f"{interpretation} Reference: {clinical}"
    return label, interpretation


def classify_measurement(
    name: str,
    value: float,
    ethnic_profile: str = "Caucasian",
    protocol_id: str = "core_lateral",
) -> Dict[str, Any]:
    default = _default_norm(name, ethnic_profile)
    mean, sd, norm_meta = get_norm_tuple(protocol_id, name, ethnic_profile, default=default)
    lower = mean - sd
    upper = mean + sd
    diff = value - mean

    if abs(diff) <= sd:
        status = "normal"
    elif diff > 0:
        status = "high"
    else:
        status = "low"

    label, interpretation = _interpret_measurement(
        name,
        diff,
        sd,
        norm_meta.get("clinical"),
    )

    return {
        "norm_mean": mean,
        "norm_sd": sd,
        "normal_min": round(lower, 2),
        "normal_max": round(upper, 2),
        "difference": round(diff, 2),
        "status": status,
        "label": label,
        "interpretation": interpretation,
        "norm_source": norm_meta.get("source"),
        "norm_protocol": norm_meta.get("protocol_ref"),
        "clinical_reference": norm_meta.get("clinical"),
        "norm_description": norm_meta.get("description"),
    }


def build_analysis_report(
    landmarks: List[Dict[str, Any]],
    px_to_mm: float = 1.0,
    ethnic_profile: str = "Caucasian",
    protocol_id: str = "core_lateral",
) -> Dict[str, Any]:
    from .protocols import get_protocol, validate_protocol_landmarks

    protocol = get_protocol(protocol_id)
    measurements = compute_cephalometric_measurements(landmarks, px_to_mm)
    rows = []
    for name in protocol["measurements"]:
        if name not in measurements:
            continue
        value = measurements[name]
        classification = classify_measurement(
            name,
            value,
            ethnic_profile=ethnic_profile,
            protocol_id=protocol_id,
        )
        rows.append(
            {
                "measurement": name,
                "group": MEASUREMENT_GROUPS.get(name, "Other"),
                "unit": MEASUREMENT_UNITS.get(name, ""),
                "value": value,
                **classification,
            }
        )

    validation = validate_protocol_landmarks(protocol_id, landmarks)

    return {
        "protocol": protocol["name"],
        "protocol_id": protocol_id,
        "norm_protocol": protocol.get("norm_protocol"),
        "ethnic_profile": ethnic_profile,
        "px_to_mm": px_to_mm,
        "landmarks": landmarks,
        "measurements": rows,
        "missing_required_landmarks": validation["missing_required_landmarks"],
        "missing_by_measurement": validation.get("missing_by_measurement", {}),
        "is_protocol_ready": validation["is_ready"],
        "landmark_count": len(landmarks),
    }
