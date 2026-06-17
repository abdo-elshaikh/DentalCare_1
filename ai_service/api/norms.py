"""Load cephalometric protocol norms from references/landmark_groups.json."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

_REFERENCES_DIR = os.path.join(os.path.dirname(__file__), "..", "references")
_LANDMARK_GROUPS_PATH = os.path.join(_REFERENCES_DIR, "landmark_groups.json")
_ANALYSIS_PROTOCOLS_PATH = os.path.join(_REFERENCES_DIR, "analysis_protocols.json")

_NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")

# Canonical measurement keys used by compute_cephalometric_measurements / classify_measurement.
MEASUREMENT_ALIASES: Dict[str, str] = {
    "SNA (°)": "SNA",
    "SNB (°)": "SNB",
    "ANB (°)": "ANB",
    "SN-GoGn (°)": "SN-GoGn",
    "MM angle (SN-GoGn) (°)": "SN-GoGn",
    "FMA (FH-MP) (°)": "FMA (FH-MP)",
    "Mandibular plane angle (FH-MP) (°)": "FMA (FH-MP)",
    "FMA (FH-MP)": "FMA (FH-MP)",
    "FMA": "FMA (FH-MP)",
    "Mandibular plane angle (FH-MP)": "FMA (FH-MP)",
    "Facial Angle (N-S-Gn)": "Facial Angle (N-S-Gn)",
    "Facial angle (FH-Na-Pg) (°)": "Facial Angle (N-S-Gn)",
    "Interincisal angle (°)": "Interincisal angle",
    "IMPA (L1-MP) (°)": "IMPA",
    "IMPA": "IMPA",
    "FMIA (°)": "FMIA",
    "Lower anterior face height (ANS-Me) (mm)": "Lower anterior facial height",
    "Nasolabial angle (°)": "Nasolabial angle",
    "U1-NA (mm)": "Upper incisor to NA (mm)",
    "U1-NA (°)": "Upper incisor to NA (deg)",
    "L1-NB (mm)": "Lower incisor to NB (mm)",
    "L1-NB (°)": "Lower incisor to NB (deg)",
    "Upper incisor to SN (°)": "Upper incisor to SN (deg)",
    "Lower incisor to mandibular plane (°)": "IMPA",
    "Articular angle (S-Ar-Go) (°)": "Articular angle (S-Ar-Go)",
    "Gonial angle (Ar-Go-Me) (°)": "Gonial angle (Ar-Go-Me)",
    "Posterior face height / Anterior face height (S-Go / N-Me) ratio": "Posterior face height / Anterior face height (S-Go / N-Me) ratio",
    "Facial height ratio (S-Go / N-Me)": "Posterior face height / Anterior face height (S-Go / N-Me) ratio",
    "Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me) (°)": "Sum of angles (N-S-Ar + S-Ar-Go + Ar-Go-Me)",
}

# Protocol slug in API -> key in landmark_groups.json "protocols".
PROTOCOL_REF_KEYS: Dict[str, str] = {
    "steiner": "Steiner",
    "eastman": "Eastman",
    "eastman_basic": "Eastman",
    "abo_american": "ABO_American",
    "tweed": "Tweed",
    "downs": "Downs",
    "mcnamara": "McNamara",
    "ricketts": "Ricketts",
    "jarabak": "Jarabak",
    "burstone": "Burstone",
    "core_lateral": "Steiner",
    "vertical_basic": "Tweed",
}

ETHNIC_TO_ANALYSIS_KEY = {
    "Caucasian": "Caucasian",
    "East Asian": "East Asian",
    "Middle Eastern": "Middle Eastern",
}


def _parse_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    match = _NUMERIC_RE.search(text.replace(",", ""))
    if not match:
        return None
    return float(match.group())


def _canonical_name(ref_name: str) -> str:
    return MEASUREMENT_ALIASES.get(ref_name, ref_name)


@lru_cache(maxsize=1)
def load_landmark_groups() -> Dict[str, Any]:
    with open(_LANDMARK_GROUPS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_analysis_protocols() -> Dict[str, Any]:
    with open(_ANALYSIS_PROTOCOLS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def list_reference_protocols() -> List[Dict[str, Any]]:
    """Summaries of literature protocols from landmark_groups.json."""
    data = load_landmark_groups()
    items = []
    for key, protocol in data.get("protocols", {}).items():
        measurements = [
            _canonical_name(entry.get("name", ""))
            for entry in protocol.get("measurements", [])
            if entry.get("name")
        ]
        items.append(
            {
                "ref_key": key,
                "description": protocol.get("description", ""),
                "measurement_count": len(measurements),
                "measurements": measurements,
            }
        )
    return items


def _norm_from_landmark_groups_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    mean = _parse_numeric(entry.get("mean")) or _parse_numeric(entry.get("ideal"))
    sd = _parse_numeric(entry.get("sd"))
    range_text = entry.get("range")
    if mean is not None and sd is None and range_text:
        parts = re.findall(r"-?\d+(?:\.\d+)?", str(range_text))
        if len(parts) >= 2:
            low, high = float(parts[0]), float(parts[1])
            sd = max((high - low) / 2.0, 0.5)
    return {
        "norm_mean": mean,
        "norm_sd": sd,
        "range": range_text,
        "clinical": entry.get("clinical"),
        "description": entry.get("description"),
        "source": "landmark_groups",
    }


def _norm_from_analysis_protocols(
    protocol_key: str,
    measurement_key: str,
    ethnic_profile: str,
) -> Optional[Dict[str, Any]]:
    data = load_analysis_protocols()
    norms = data.get("norms", {}).get(protocol_key, {})
    entry = norms.get(measurement_key)
    if not entry:
        return None
    ethnic_key = ETHNIC_TO_ANALYSIS_KEY.get(ethnic_profile, "Caucasian")
    ref_block = entry.get("reference", {}).get(ethnic_key) or entry.get("reference", {}).get("Caucasian")
    if not ref_block:
        return None
    stats = ref_block.get("Both") or next(iter(ref_block.values()), None)
    if not stats:
        return None
    return {
        "norm_mean": stats.get("mean"),
        "norm_sd": stats.get("sd"),
        "range": stats.get("range"),
        "clinical": None,
        "description": entry.get("description"),
        "source": "analysis_protocols",
    }


def get_measurement_norm(
    protocol_id: str,
    measurement_key: str,
    ethnic_profile: str = "Caucasian",
) -> Dict[str, Any]:
    """Return mean/sd and metadata for a measurement under a clinical protocol."""
    ref_key = PROTOCOL_REF_KEYS.get(protocol_id, protocol_id)
    groups = load_landmark_groups()
    protocol_block = groups.get("protocols", {}).get(ref_key, {})

    norm: Dict[str, Any] = {
        "norm_mean": None,
        "norm_sd": None,
        "range": None,
        "clinical": None,
        "description": None,
        "source": None,
        "protocol_ref": ref_key,
    }

    analysis_key = ref_key if ref_key in load_analysis_protocols().get("norms", {}) else protocol_id
    if analysis_key not in ("core_lateral", "eastman_basic", "vertical_basic"):
        ethnic_norm = _norm_from_analysis_protocols(analysis_key, measurement_key, ethnic_profile)
        if ethnic_norm:
            norm.update({k: v for k, v in ethnic_norm.items() if v is not None})

    for entry in protocol_block.get("measurements", []):
        ref_name = entry.get("name", "")
        if _canonical_name(ref_name) != measurement_key:
            continue
        parsed = _norm_from_landmark_groups_entry(entry)
        if ethnic_profile == "Caucasian" or norm["norm_mean"] is None:
            for key, value in parsed.items():
                if norm.get(key) is None and value is not None:
                    norm[key] = value
        else:
            for key in ("clinical", "description", "range"):
                if norm.get(key) is None and parsed.get(key) is not None:
                    norm[key] = parsed[key]
        if norm["source"] is None and parsed.get("source"):
            norm["source"] = parsed["source"]
        break

    if norm["norm_mean"] is None or norm["norm_sd"] is None:
        fallback = _norm_from_analysis_protocols(analysis_key, measurement_key, ethnic_profile)
        if fallback:
            for key, value in fallback.items():
                if norm.get(key) is None and value is not None:
                    norm[key] = value

    return norm


def get_norm_tuple(
    protocol_id: str,
    measurement_key: str,
    ethnic_profile: str = "Caucasian",
    default: Tuple[float, float] = (80.0, 2.0),
) -> Tuple[float, float, Dict[str, Any]]:
    meta = get_measurement_norm(protocol_id, measurement_key, ethnic_profile)
    mean = meta.get("norm_mean")
    sd = meta.get("norm_sd")
    if mean is None or sd is None:
        return default[0], default[1], meta
    return float(mean), float(sd), meta
