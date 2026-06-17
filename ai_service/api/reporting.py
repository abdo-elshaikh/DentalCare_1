import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List


def analysis_to_csv(analysis: Dict[str, Any]) -> str:
    output = io.StringIO()
    fieldnames = [
        "group",
        "measurement",
        "unit",
        "mean",
        "sd",
        "normal_min",
        "normal_max",
        "value",
        "difference",
        "status",
        "label",
        "interpretation",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in analysis.get("measurements", []):
        writer.writerow(row)
    return output.getvalue()


def landmarks_to_csv(landmarks: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    fieldnames = ["id", "name", "x", "y", "score", "accepted"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in landmarks:
        writer.writerow(row)
    return output.getvalue()


def build_result_payload(
    landmarks: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        },
        "landmarks": landmarks,
        "analysis": analysis,
    }


def build_result_zip(
    landmarks: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    metadata: Dict[str, Any] | None = None,
) -> bytes:
    payload = build_result_payload(landmarks, analysis, metadata)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("result.json", json.dumps(payload, indent=2))
        zf.writestr("landmarks.csv", landmarks_to_csv(landmarks))
        zf.writestr("measurements.csv", analysis_to_csv(analysis))
    return buffer.getvalue()
