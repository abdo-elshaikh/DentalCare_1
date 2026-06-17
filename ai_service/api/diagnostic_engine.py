from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from .analysis import build_analysis_report
from .measurement_analysis import detect_measurement_outliers


PRIMARY_PROTOCOLS = ["steiner", "tweed", "downs", "mcnamara", "jarabak"]


def _measurements_map(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {row["measurement"]: row for row in report.get("measurements", [])}


def _z_score(row: Dict[str, Any]) -> float:
    sd = float(row.get("sd") or 0.0)
    if sd <= 0:
        return abs(float(row.get("difference") or 0.0))
    return abs(float(row.get("difference") or 0.0)) / sd


def _severity_from_rows(rows: Iterable[Dict[str, Any]]) -> str:
    rows = list(rows)
    if not rows:
        return "mild"

    abnormal = [row for row in rows if row.get("status") != "normal"]
    max_z = max((_z_score(row) for row in abnormal), default=0.0)

    if max_z >= 2.5 or len(abnormal) >= 4:
        return "severe"
    if max_z >= 1.5 or len(abnormal) >= 2:
        return "moderate"
    return "mild"


def _confidence_from_evidence(
    rows: List[Dict[str, Any]],
    missing_by_measurement: Dict[str, Any],
    outlier_count: int,
    is_protocol_ready: bool,
) -> float:
    """Estimate confidence from evidence coverage, not from diagnostic severity."""
    present_count = len(rows)
    missing_count = len(missing_by_measurement)
    evidence_total = present_count + missing_count

    coverage = present_count / evidence_total if evidence_total else 1.0
    outlier_ratio = (outlier_count / present_count) if present_count else 0.0

    confidence = 0.18 + (0.72 * coverage) - min(0.20, outlier_ratio * 0.10)
    if not is_protocol_ready:
        confidence -= 0.05

    return max(0.15, min(0.98, confidence))


def _skeletal_class(rows_by_measurement: Dict[str, Dict[str, Any]]) -> Tuple[str, str]:
    anb = rows_by_measurement.get("ANB")
    sna = rows_by_measurement.get("SNA")
    snb = rows_by_measurement.get("SNB")

    # Hard clinical thresholds based on modern scientific methodologies
    if anb:
        val = float(anb.get("value", 3.0))
        if val >= 4.5:
            return "Class II", "CII"
        if val <= 1.0:
            return "Class III", "CIII"
        return "Class I", "CI"

    if sna and snb:
        if float(sna.get("difference", 0.0)) > 0 and float(snb.get("difference", 0.0)) < 0:
            return "Class II", "CII"
        if float(sna.get("difference", 0.0)) < 0 and float(snb.get("difference", 0.0)) > 0:
            return "Class III", "CIII"

    return "Class I", "CI"


def _vertical_pattern(rows_by_measurement: Dict[str, Dict[str, Any]]) -> Tuple[str, str]:
    ratio = rows_by_measurement.get("Posterior face height / Anterior face height (S-Go / N-Me) ratio")
    fma = rows_by_measurement.get("FMA (FH-MP)")
    sn_gogn = rows_by_measurement.get("SN-GoGn")

    if ratio:
        label = ratio.get("label", "")
        if "Increased" in label or "vertical" in label.lower():
            return "Hyperdivergent", "HVD"
        if "Decreased" in label:
            return "Hypodivergent", "LVD"

    high_count = sum(1 for row in (fma, sn_gogn) if row and float(row.get("difference", 0.0)) > 0)
    low_count = sum(1 for row in (fma, sn_gogn) if row and float(row.get("difference", 0.0)) < 0)

    if high_count > low_count:
        return "Hyperdivergent", "HVD"
    if low_count > high_count:
        return "Hypodivergent", "LVD"
    return "Normodivergent", "NVD"


def _dental_pattern(rows_by_measurement: Dict[str, Dict[str, Any]]) -> str:
    impa = rows_by_measurement.get("IMPA")
    fmia = rows_by_measurement.get("FMIA")
    interincisal = rows_by_measurement.get("Interincisal angle")

    if impa and float(impa.get("difference", 0.0)) > 0:
        return "proclined lower incisors"
    if impa and float(impa.get("difference", 0.0)) < 0:
        return "retroclined lower incisors"
    if fmia and float(fmia.get("difference", 0.0)) < 0:
        return "proclined lower incisors"
    if interincisal and float(interincisal.get("difference", 0.0)) < 0:
        return "increased dental compensation"
    return "balanced incisor inclination"


def _craniofacial_patterns(rows_by_measurement: Dict[str, Dict[str, Any]]) -> List[str]:
    patterns = []
    sna = rows_by_measurement.get("SNA")
    snb = rows_by_measurement.get("SNB")
    
    if sna:
        diff = float(sna.get("difference", 0.0))
        sd = float(sna.get("sd", 1.0))
        if diff > sd:
            patterns.append("Maxillary Hyperplasia (Prognathism)")
        elif diff < -sd:
            patterns.append("Maxillary Hypoplasia (Retrognathism)")
            
    if snb:
        diff = float(snb.get("difference", 0.0))
        sd = float(snb.get("sd", 1.0))
        if diff > sd:
            patterns.append("Mandibular Hyperplasia (Prognathism)")
        elif diff < -sd:
            patterns.append("Mandibular Hypoplasia (Retrognathism)")
            
    if not patterns:
        patterns.append("Balanced Craniofacial Pattern")
        
    return patterns


def _suggest_icd10_codes(skeletal_class: str, patterns: List[str], vertical_pattern: str) -> List[Dict[str, str]]:
    codes = []
    
    if "Class II" in skeletal_class:
        codes.append({"code": "K07.11", "description": "Maxillary asymmetry / prognathism"})
        codes.append({"code": "K07.22", "description": "Disto-occlusion (Class II malocclusion)"})
    elif "Class III" in skeletal_class:
        codes.append({"code": "K07.12", "description": "Mandibular asymmetry / prognathism"})
        codes.append({"code": "K07.23", "description": "Mesio-occlusion (Class III malocclusion)"})
    else:
        codes.append({"code": "K07.21", "description": "Neutro-occlusion (Class I malocclusion)"})
        
    if any("Maxillary Hypoplasia" in p for p in patterns):
        codes.append({"code": "K07.01", "description": "Major anomalies of jaw size: Maxillary hypoplasia"})
    if any("Mandibular Hypoplasia" in p for p in patterns):
        codes.append({"code": "K07.03", "description": "Major anomalies of jaw size: Mandibular hypoplasia"})
    if any("Maxillary Hyperplasia" in p for p in patterns):
        codes.append({"code": "K07.02", "description": "Major anomalies of jaw size: Maxillary hyperplasia"})
    if any("Mandibular Hyperplasia" in p for p in patterns):
        codes.append({"code": "K07.04", "description": "Major anomalies of jaw size: Mandibular hyperplasia"})
        
    if "Hyperdivergent" in vertical_pattern:
        codes.append({"code": "K07.19", "description": "Anomalies of jaw-cranial base relationship, unspecified (Vertical excess)"})
    elif "Hypodivergent" in vertical_pattern:
        codes.append({"code": "K07.19", "description": "Anomalies of jaw-cranial base relationship, unspecified (Vertical deficiency)"})
        
    return codes


def _finding_from_row(row: Dict[str, Any], is_outlier: bool = False) -> Dict[str, Any]:
    finding = {
        "measurement": row.get("measurement"),
        "value": row.get("value"),
        "mean": row.get("mean"),
        "difference": row.get("difference"),
        "label": row.get("label"),
        "interpretation": row.get("interpretation"),
        "status": row.get("status"),
        "group": row.get("group"),
    }
    if is_outlier:
        finding["is_outlier"] = True
        finding["outlier_warning"] = "WARNING: This measurement is a statistical outlier and may be due to a landmark detection error. Do not rely heavily on it."
    return finding


def diagnose_measurements(
    measurements_report: Dict[str, Any],
    age: Optional[int] = None,
    sex: Optional[str] = None,
) -> Dict[str, Any]:
    rows = list(measurements_report.get("measurements", []))
    rows_by_measurement = _measurements_map(measurements_report)
    
    ethnic_profile = measurements_report.get("ethnic_profile", "Caucasian")
    
    # Run IQR Outlier Detection
    raw_measurements = {row["measurement"]: row["value"] for row in rows}
    outliers_dict = detect_measurement_outliers(raw_measurements, ethnic_profile)

    skeletal_class, skeletal_code = _skeletal_class(rows_by_measurement)
    vertical_pattern, vertical_code = _vertical_pattern(rows_by_measurement)
    severity = _severity_from_rows(rows)
    severity_code = {"mild": "L", "moderate": "M", "severe": "S"}[severity]
    diagnostic_code = f"{skeletal_code}-{vertical_code}-{severity_code}"
    
    craniofacial_patterns = _craniofacial_patterns(rows_by_measurement)
    icd10_codes = _suggest_icd10_codes(skeletal_class, craniofacial_patterns, vertical_pattern)

    findings: List[Dict[str, Any]] = []
    outlier_count = 0
    for name in ("ANB", "SNA", "SNB", "FMA (FH-MP)", "SN-GoGn", "IMPA", "FMIA", "Interincisal angle", "Lower anterior facial height", "Nasolabial angle", "Posterior face height / Anterior face height (S-Go / N-Me) ratio", "Articular angle (S-Ar-Go)", "Gonial angle (Ar-Go-Me)"):
        row = rows_by_measurement.get(name)
        if not row:
            continue
        
        is_outlier = outliers_dict.get(name, False)
        if is_outlier:
            outlier_count += 1
            
        if row.get("status") == "normal" and not is_outlier:
            continue
            
        findings.append(_finding_from_row(row, is_outlier=is_outlier))

    if not findings and rows:
        findings.append(_finding_from_row(rows[0]))

    protocol_snapshots = []
    for protocol_id in PRIMARY_PROTOCOLS:
        report = build_analysis_report(
            measurements_report.get("landmarks", []),
            px_to_mm=measurements_report.get("px_to_mm", 1.0),
            ethnic_profile=ethnic_profile,
            protocol_id=protocol_id,
        )
        protocol_snapshots.append(
            {
                "protocol_id": protocol_id,
                "protocol": report.get("protocol"),
                "measurements": report.get("measurements", []),
                "is_protocol_ready": report.get("is_protocol_ready", False),
            }
        )

    confidence = _confidence_from_evidence(
        rows,
        measurements_report.get("missing_by_measurement", {}),
        outlier_count,
        bool(measurements_report.get("is_protocol_ready", False)),
    )
    
    # Build a concise professional summary
    top_findings = findings[:4]
    summary_parts = [f"Skeletal class: {skeletal_class}", f"Vertical pattern: {vertical_pattern}", f"Severity: {severity}"]
    if top_findings:
        summary_parts.append("Key findings: " + ", ".join(f.get("measurement") or "" for f in top_findings))
    professional_summary = ". ".join(summary_parts) + "."

    # Actionable recommendations based on severity/patterns
    recommendations: List[str] = []
    if outlier_count > 0:
        recommendations.append(f"CRITICAL: {outlier_count} measurement(s) detected as statistical outliers. Highly recommend reviewing and refining landmark placements.")
        
    if severity in ("severe", "moderate"):
        recommendations.append("Refer for specialist orthodontic assessment for skeletal correction consideration.")
    else:
        recommendations.append("Consider conservative orthodontic management with monitoring.")

    if "Class II" in skeletal_class and age is not None and age < 18:
        recommendations.append("Assess suitability for growth modification (functional appliance) while monitoring compliance.")
    if "Class III" in skeletal_class and age is not None and age >= 18:
        recommendations.append("Consider orthognathic consultation for definitive skeletal correction.")

    # Pack the enriched report
    return {
        "protocol": measurements_report.get("protocol"),
        "protocol_id": measurements_report.get("protocol_id"),
        "norm_protocol": measurements_report.get("norm_protocol"),
        "age": age,
        "sex": sex,
        "skeletal_class": skeletal_class,
        "vertical_pattern": vertical_pattern,
        "severity": severity,
        "diagnostic_code": diagnostic_code,
        "craniofacial_patterns": craniofacial_patterns,
        "icd10_codes": icd10_codes,
        "findings": findings,
        "measurement_rows": rows,
        "protocol_snapshots": protocol_snapshots,
        "dental_pattern": _dental_pattern(rows_by_measurement),
        "confidence": round(confidence, 2),
        "missing_by_measurement": measurements_report.get("missing_by_measurement", {}),
        "is_protocol_ready": measurements_report.get("is_protocol_ready", False),
        "professional_summary": professional_summary,
        "recommendations": recommendations,
    }


def diagnose_landmarks(
    landmarks: List[Dict[str, Any]],
    px_to_mm: float = 1.0,
    ethnic_profile: str = "Caucasian",
    protocol_id: str = "steiner",
    age: Optional[int] = None,
    sex: Optional[str] = None,
) -> Dict[str, Any]:
    analysis = build_analysis_report(
        landmarks,
        px_to_mm=px_to_mm,
        ethnic_profile=ethnic_profile,
        protocol_id=protocol_id,
    )
    enriched = dict(analysis)
    enriched["landmarks"] = landmarks
    return diagnose_measurements(enriched, age=age, sex=sex)


def build_diagnostic_report(
    landmarks: List[Dict[str, Any]],
    px_to_mm: float = 1.0,
    ethnic_profile: str = "Caucasian",
    protocol_id: str = "steiner",
    age: Optional[int] = None,
    sex: Optional[str] = None,
) -> Dict[str, Any]:
    report = diagnose_landmarks(
        landmarks,
        px_to_mm=px_to_mm,
        ethnic_profile=ethnic_profile,
        protocol_id=protocol_id,
        age=age,
        sex=sex,
    )
    return report
