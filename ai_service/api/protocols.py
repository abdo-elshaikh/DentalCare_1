from typing import Any, Dict, Iterable, List

from .analysis import LANDMARK_NAMES
from .norms import PROTOCOL_REF_KEYS, get_measurement_norm, list_reference_protocols


# Measurements the 19-landmark model can compute today.
_COMPUTABLE_MEASUREMENTS = {
    "SNA": [1, 2, 5],
    "SNB": [1, 2, 6],
    "ANB": [1, 2, 5, 6],
    "Facial Angle (N-S-Gn)": [1, 2, 9],
    "FMA (FH-MP)": [3, 4, 8, 10],
    "SN-GoGn": [1, 2, 9, 10],
    "IMPA": [6, 8, 10, 11],
    "FMIA": [3, 4, 6, 8, 10, 11],
    "Interincisal angle": [5, 6, 11, 12],
    "Lower anterior facial height": [8, 18],
    "Nasolabial angle": [13, 14, 15],
    "Articular angle (S-Ar-Go)": [1, 10, 19],
    "Gonial angle (Ar-Go-Me)": [8, 10, 19],
    "Posterior face height / Anterior face height (S-Go / N-Me) ratio": [1, 2, 8, 10],
    "Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me)": [1, 2, 8, 10, 19],
}

PROTOCOLS: Dict[str, Dict[str, Any]] = {
    "core_lateral": {
        "id": "core_lateral",
        "name": "Core lateral cephalometric screening",
        "view": "lateral",
        "description": "Core skeletal and vertical measurements supported by the current 19-landmark model.",
        "norm_protocol": "Steiner",
        "required_landmark_ids": [1, 2, 3, 4, 5, 6, 8, 9, 10],
        "measurements": ["SNA", "SNB", "ANB", "FMA (FH-MP)", "Facial Angle (N-S-Gn)"],
    },
    "steiner": {
        "id": "steiner",
        "name": "Steiner analysis",
        "view": "lateral",
        "description": "Steiner skeletal and vertical screening using literature norms from landmark_groups.json.",
        "norm_protocol": "Steiner",
        "required_landmark_ids": [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12],
        "measurements": ["SNA", "SNB", "ANB", "SN-GoGn", "FMA (FH-MP)", "IMPA", "FMIA", "Interincisal angle"],
    },
    "eastman_basic": {
        "id": "eastman_basic",
        "name": "Eastman basic",
        "view": "lateral",
        "description": "Eastman-style skeletal subset with UK Caucasian reference norms.",
        "norm_protocol": "Eastman",
        "required_landmark_ids": [1, 2, 5, 6],
        "measurements": ["SNA", "SNB", "ANB"],
    },
    "eastman": {
        "id": "eastman",
        "name": "Eastman analysis",
        "view": "lateral",
        "description": "Eastman skeletal and vertical subset available from the current model.",
        "norm_protocol": "Eastman",
        "required_landmark_ids": [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12],
        "measurements": [
            "SNA",
            "SNB",
            "ANB",
            "FMA (FH-MP)",
            "SN-GoGn",
            "Interincisal angle",
        ],
    },
    "abo_american": {
        "id": "abo_american",
        "name": "ABO American Board screening",
        "view": "lateral",
        "description": "ABO-recommended Steiner-style norms with range-based clinical targets.",
        "norm_protocol": "ABO_American",
        "required_landmark_ids": [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12],
        "measurements": ["SNA", "SNB", "ANB", "SN-GoGn", "FMA (FH-MP)", "Interincisal angle"],
    },
    "tweed": {
        "id": "tweed",
        "name": "Tweed triangle",
        "view": "lateral",
        "description": "Frankfort-mandibular plane, incisor-mandibular plane, and derived FMIA.",
        "norm_protocol": "Tweed",
        "required_landmark_ids": [3, 4, 6, 8, 10, 11],
        "measurements": ["FMA (FH-MP)", "IMPA", "FMIA"],
    },
    "downs": {
        "id": "downs",
        "name": "Downs vertical screening",
        "view": "lateral",
        "description": "Downs mandibular plane and interincisal norms where landmarks permit.",
        "norm_protocol": "Downs",
        "required_landmark_ids": [3, 4, 6, 8, 10, 11, 12],
        "measurements": ["FMA (FH-MP)", "Interincisal angle"],
    },
    "mcnamara": {
        "id": "mcnamara",
        "name": "McNamara screening",
        "view": "lateral",
        "description": "McNamara anterior face height and nasolabial subset supported by current landmarks.",
        "norm_protocol": "McNamara",
        "required_landmark_ids": [8, 13, 14, 15, 18],
        "measurements": ["Lower anterior facial height", "Nasolabial angle"],
    },
    "jarabak": {
        "id": "jarabak",
        "name": "Jarabak analysis",
        "view": "lateral",
        "description": "Jarabak skeletal assessment using face-height ratio and cranial base angles.",
        "norm_protocol": "Jarabak",
        "required_landmark_ids": [1, 2, 8, 10, 19],
        "measurements": [
            "Articular angle (S-Ar-Go)",
            "Gonial angle (Ar-Go-Me)",
            "Posterior face height / Anterior face height (S-Go / N-Me) ratio",
            "Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me)",
        ],
    },
    "vertical_basic": {
        "id": "vertical_basic",
        "name": "Vertical pattern basic",
        "view": "lateral",
        "description": "Frankfort-mandibular and facial-axis screening subset.",
        "norm_protocol": "Tweed",
        "required_landmark_ids": [1, 2, 3, 4, 8, 9, 10],
        "measurements": ["FMA (FH-MP)", "Facial Angle (N-S-Gn)"],
    },
}


def list_protocols() -> List[Dict[str, Any]]:
    ref_meta = {item["ref_key"]: item for item in list_reference_protocols()}
    rows = []
    for protocol in PROTOCOLS.values():
        ref_key = protocol.get("norm_protocol") or PROTOCOL_REF_KEYS.get(protocol["id"])
        ref = ref_meta.get(ref_key, {})
        rows.append(
            {
                "id": protocol["id"],
                "name": protocol["name"],
                "view": protocol["view"],
                "description": protocol["description"],
                "norm_protocol": ref_key,
                "required_landmark_ids": protocol["required_landmark_ids"],
                "measurements": protocol["measurements"],
                "reference_measurement_count": ref.get("measurement_count"),
            }
        )
    return rows


def get_protocol(protocol_id: str) -> Dict[str, Any]:
    if protocol_id not in PROTOCOLS:
        raise ValueError(f"unknown protocol: {protocol_id}")
    protocol = dict(PROTOCOLS[protocol_id])
    protocol["computable_measurements"] = {
        name: _COMPUTABLE_MEASUREMENTS.get(name, [])
        for name in protocol["measurements"]
    }
    return protocol


def get_protocol_norms_preview(protocol_id: str) -> List[Dict[str, Any]]:
    protocol = get_protocol(protocol_id)
    norm_protocol = protocol.get("norm_protocol") or PROTOCOL_REF_KEYS.get(protocol_id, protocol_id)
    preview = []
    for measurement in protocol["measurements"]:
        norm = get_measurement_norm(protocol_id, measurement)
        preview.append(
            {
                "measurement": measurement,
                "mean": norm.get("norm_mean"),
                "sd": norm.get("norm_sd"),
                "range": norm.get("range"),
                "clinical": norm.get("clinical"),
                "source": norm.get("source"),
                "protocol_ref": norm_protocol,
            }
        )
    return preview


def validate_protocol_landmarks(
    protocol_id: str,
    landmarks: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    protocol = get_protocol(protocol_id)
    present_ids = {int(lm["id"]) for lm in landmarks if "id" in lm}
    missing_ids = [lm_id for lm_id in protocol["required_landmark_ids"] if lm_id not in present_ids]
    missing_by_measurement = {}
    for measurement in protocol["measurements"]:
        needed = _COMPUTABLE_MEASUREMENTS.get(measurement, [])
        missing_for_measurement = [lm_id for lm_id in needed if lm_id not in present_ids]
        if missing_for_measurement:
            missing_by_measurement[measurement] = missing_for_measurement

    return {
        "protocol_id": protocol_id,
        "protocol_name": protocol["name"],
        "norm_protocol": protocol.get("norm_protocol"),
        "is_ready": not missing_ids,
        "present_landmark_ids": sorted(present_ids),
        "missing_required_landmarks": [
            {"id": lm_id, "name": LANDMARK_NAMES.get(lm_id, f"Landmark {lm_id}")}
            for lm_id in missing_ids
        ],
        "missing_by_measurement": missing_by_measurement,
    }
