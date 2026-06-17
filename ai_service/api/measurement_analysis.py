"""Measurement Analysis Module - Phase 3.1

Advanced measurement validation, confidence intervals, and quality assessment.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class MeasurementQuality:
    """Quality assessment for a single measurement."""
    measurement_name: str
    value: float
    confidence_level: str  # "high", "medium", "low"
    ci_lower: float  # 95% confidence interval
    ci_upper: float
    is_outlier: bool
    percentile: float  # 0-100 where this measurement falls
    z_score: float
    validation_warnings: List[str]  # Any issues detected
    refinement_priority: int  # 1=most important to refine, 0=not needed


# Measurement-specific constraints for anatomical accuracy
MEASUREMENT_CONSTRAINTS = {
    # (min_value, max_value, unit, description)
    "SNA": (73.0, 89.0, "degrees", "Maxillary position, normally 78-84°"),
    "SNB": (72.0, 88.0, "degrees", "Mandibular position, normally 75-80°"),
    "ANB": (-5.0, 10.0, "degrees", "Skeletal sagittal relationship, normally 1-5°"),
    "FMA (FH-MP)": (16.0, 35.0, "degrees", "Vertical dimension, normally 22-29°"),
    "IMPA": (75.0, 105.0, "degrees", "Lower incisor inclination, normally 85-95°"),
    "FMIA": (50.0, 75.0, "degrees", "Lower incisor to mandibular plane, normally 60-70°"),
    "Interincisal angle": (115.0, 145.0, "degrees", "Incisor relationship, normally 122-135°"),
    "Nasolabial angle": (85.0, 115.0, "degrees", "Soft tissue nasolabial, normally 95-110°"),
    "Gonial angle (Ar-Go-Me)": (115.0, 145.0, "degrees", "Jaw opening, normally 120-135°"),
    "Articular angle (S-Ar-Go)": (130.0, 155.0, "degrees", "Posterior facet, normally 140-150°"),
    "Lower anterior facial height": (60.0, 80.0, "millimeters", "Lower face height normally 65-75mm"),
}

# Typical measurement relationships that should hold
MEASUREMENT_RELATIONSHIPS = [
    # (measure_a, measure_b, expected_relationship, tolerance)
    ("SNA", "SNB", "SNB_should_be_close_to_SNA", 4.0),  # Usually differ by 2-4°
    ("ANB", "SNA", "SNA_higher_than_SNB_when_positive_ANB", None),  # If ANB positive, SNA > SNB
    ("IMPA", "FMIA", "sum_normally_90_degrees", 15.0),  # IMPA + FMIA ≈ 90°
    ("FMA (FH-MP)", "SN-GoGn", "correlated_vertical_dimension", 10.0),
]


def detect_measurement_outliers(
    measurements: Dict[str, float],
    ethnic_profile: str = "Caucasian",
    outlier_threshold_z: float = 2.5,
    protocol_id: str = "core_lateral"
) -> Dict[str, bool]:
    """
    Detect outlier measurements using an IQR-inspired method.
    
    Since we only have mean and SD from norms, we approximate the bounds.
    For a normal distribution:
    Q1 ≈ mean - 0.6745 * SD
    Q3 ≈ mean + 0.6745 * SD
    IQR ≈ 1.349 * SD
    Lower Bound = Q1 - 1.5 * IQR ≈ mean - 2.698 * SD
    Upper Bound = Q3 + 1.5 * IQR ≈ mean + 2.698 * SD
    
    Returns dict mapping measurement name to whether it's an outlier.
    """
    from .norms import get_norm_tuple
    
    outliers = {}
    
    for meas_name, value in measurements.items():
        try:
            # We pass the selected protocol_id (e.g., 'core_lateral') to get_norm_tuple
            mean, sd, _ = get_norm_tuple(protocol_id, meas_name, ethnic_profile)
        except Exception:
            outliers[meas_name] = False
            continue
        
        if sd <= 0:
            outliers[meas_name] = False
            continue
        
        # IQR method approximation bounds
        lower_bound = mean - 2.698 * sd
        upper_bound = mean + 2.698 * sd
        
        val = float(value)
        outliers[meas_name] = val < lower_bound or val > upper_bound
    
    return outliers


def validate_measurement_relationships(
    measurements: Dict[str, float],
    warnings: Optional[List[str]] = None
) -> List[str]:
    """
    Check if measurements satisfy expected anatomical relationships.
    
    Returns list of relationship violations.
    """
    if warnings is None:
        warnings = []
    
    for measure_a, measure_b, relationship_type, tolerance in MEASUREMENT_RELATIONSHIPS:
        val_a = measurements.get(measure_a)
        val_b = measurements.get(measure_b)
        
        if val_a is None or val_b is None:
            continue
        
        val_a = float(val_a)
        val_b = float(val_b)
        
        if relationship_type == "SNB_should_be_close_to_SNA":
            diff = abs(val_a - val_b)
            if diff > tolerance:
                warnings.append(
                    f"{measure_a} ({val_a:.1f}°) and {measure_b} ({val_b:.1f}°) differ by "
                    f"{diff:.1f}° (expected ~{tolerance}°). Check measurement accuracy."
                )
        
        elif relationship_type == "SNA_higher_than_SNB_when_positive_ANB":
            if val_a > 0 and val_a < val_b:
                warnings.append(
                    f"{measure_b} ({val_b:.1f}°) > {measure_a} ({val_a:.1f}°) but ANB is positive. "
                    f"Recheck SNA and SNB."
                )
        
        elif relationship_type == "sum_normally_90_degrees":
            total = val_a + val_b
            if abs(total - 90) > tolerance:
                warnings.append(
                    f"{measure_a} + {measure_b} = {total:.1f}° (expected ~90°). "
                    f"Large deviation suggests refinement needed."
                )
    
    return warnings


def assess_measurement_constraint(
    measurement_name: str,
    value: float
) -> Tuple[bool, List[str]]:
    """
    Check if measurement violates anatomical bounds.
    
    Returns (is_valid, warnings).
    """
    warnings = []
    
    if measurement_name not in MEASUREMENT_CONSTRAINTS:
        return True, warnings
    
    min_val, max_val, unit, desc = MEASUREMENT_CONSTRAINTS[measurement_name]
    
    if value < min_val:
        warnings.append(
            f"{measurement_name} = {value:.1f}{unit} is below normal range "
            f"({min_val:.1f}-{max_val:.1f}). Recheck landmarks."
        )
        return False, warnings
    
    if value > max_val:
        warnings.append(
            f"{measurement_name} = {value:.1f}{unit} is above normal range "
            f"({min_val:.1f}-{max_val:.1f}). Recheck landmarks."
        )
        return False, warnings
    
    return True, warnings


def calculate_confidence_intervals(
    measurements_with_uncertainty: Dict[str, Dict[str, float]],
    confidence_level: float = 0.95
) -> Dict[str, Dict[str, float]]:
    """
    Calculate confidence intervals from measurement uncertainty data.
    
    Input format (from measurements.py):
    {
        "ANB": {"value": 5.2, "mean": 5.2, "sd": 0.8},
        ...
    }
    
    Returns with 95% CI added:
    {
        "ANB": {
            "value": 5.2,
            "mean": 5.2,
            "sd": 0.8,
            "ci_lower": 3.7,
            "ci_upper": 6.7,
            "ci_margin": 1.5
        },
        ...
    }
    """
    # Z-score for 95% confidence interval
    z_critical = 1.96 if confidence_level == 0.95 else 1.645
    
    result = {}
    
    for meas_name, data in measurements_with_uncertainty.items():
        mean = float(data.get("mean", data.get("value", 0.0)))
        sd = float(data.get("sd", 0.0))
        
        margin = z_critical * sd if sd > 0 else 0
        
        result[meas_name] = {
            **data,
            "ci_lower": round(mean - margin, 2),
            "ci_upper": round(mean + margin, 2),
            "ci_margin": round(margin, 2),
            "ci_level": confidence_level
        }
    
    return result


def assess_measurement_quality(
    measurements_with_ci: Dict[str, Dict[str, float]],
    protocol_id: str = "core_lateral",
    ethnic_profile: str = "Caucasian",
    px_to_mm: float = 1.0,
    high_uncertainty_threshold: float = 2.0  # degrees or mm
) -> Dict[str, MeasurementQuality]:
    """
    Comprehensive quality assessment for each measurement.
    
    Returns dict with MeasurementQuality for each measurement.
    """
    from .norms import get_norm_tuple
    
    quality_reports = {}
    outliers = detect_measurement_outliers(
        {k: v.get("value", 0) for k, v in measurements_with_ci.items()},
        ethnic_profile=ethnic_profile,
        protocol_id=protocol_id
    )
    
    for meas_name, data in measurements_with_ci.items():
        value = float(data.get("value", 0.0))
        sd = float(data.get("sd", 0.0))
        ci_lower = float(data.get("ci_lower", value))
        ci_upper = float(data.get("ci_upper", value))
        
        # Get norm
        try:
            mean, norm_sd, _ = get_norm_tuple(protocol_id, meas_name, ethnic_profile)
        except Exception:
            mean, norm_sd = value, sd or 1.0
        
        # Z-score
        z_score = (value - mean) / norm_sd if norm_sd > 0 else 0.0
        
        # Percentile (rough approximation)
        percentile = 50.0 + (z_score * 15.87)  # Assumes ~85% at 1 SD
        percentile = max(0.1, min(99.9, percentile))
        
        # Confidence level
        ci_width = ci_upper - ci_lower
        if ci_width < 0.5:
            confidence = "high"
        elif ci_width < 1.5:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Validation warnings
        warnings = []
        
        # Check constraints
        is_valid, constraint_warnings = assess_measurement_constraint(meas_name, value)
        warnings.extend(constraint_warnings)
        
        # Check uncertainty
        if sd > high_uncertainty_threshold:
            warnings.append(
                f"High uncertainty (SD={sd:.1f}). Consider landmark refinement."
            )
        
        # Check if outlier
        is_outlier = outliers.get(meas_name, False)
        if is_outlier:
            warnings.append(
                f"Measurement is statistical outlier (Z={z_score:.1f}). "
                f"Recheck landmark placement."
            )
        
        # Determine refinement priority
        refinement_priority = 0
        if is_outlier:
            refinement_priority = 1  # High priority
        elif sd > high_uncertainty_threshold:
            refinement_priority = 2  # Medium priority
        elif not is_valid:
            refinement_priority = 3  # Low-medium priority
        
        quality_reports[meas_name] = MeasurementQuality(
            measurement_name=meas_name,
            value=value,
            confidence_level=confidence,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            is_outlier=is_outlier,
            percentile=percentile,
            z_score=z_score,
            validation_warnings=warnings,
            refinement_priority=refinement_priority
        )
    
    return quality_reports


def suggest_landmark_refinement(
    quality_reports: Dict[str, MeasurementQuality],
    landmarks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Suggest which landmarks to refine based on measurement quality.
    
    Returns list of landmarks with refinement recommendations.
    """
    # Map measurements to landmarks
    measurement_to_landmarks = {
        "ANB": ["A", "N", "B"],
        "SNA": ["S", "N", "A"],
        "SNB": ["S", "N", "B"],
        "FMA (FH-MP)": ["N", "S", "Go", "Me"],
        "IMPA": ["I", "M", "A"],  # Approximation
        "Nasolabial angle": ["N", "A", "UL"],
        # Add more as needed
    }
    
    landmarks_needing_refinement = {}
    
    for meas_name, quality in quality_reports.items():
        if quality.refinement_priority > 0 and meas_name in measurement_to_landmarks:
            for lm_id in measurement_to_landmarks[meas_name]:
                if lm_id not in landmarks_needing_refinement:
                    landmarks_needing_refinement[lm_id] = {
                        "landmark_id": lm_id,
                        "related_measurements": [],
                        "total_priority": 0
                    }
                landmarks_needing_refinement[lm_id]["related_measurements"].append(meas_name)
                landmarks_needing_refinement[lm_id]["total_priority"] += quality.refinement_priority
    
    # Sort by priority
    suggestions = sorted(
        landmarks_needing_refinement.values(),
        key=lambda x: x["total_priority"],
        reverse=True
    )
    
    # Add confidence info
    lm_map = {lm.get("id"): lm for lm in landmarks}
    for suggestion in suggestions:
        lm_id = suggestion["landmark_id"]
        if lm_id in lm_map:
            suggestion["confidence"] = lm_map[lm_id].get("score", 0.95)
        suggestion["recommendation"] = (
            f"Refine {lm_id}: used in {len(suggestion['related_measurements'])} measurements"
        )
    
    return suggestions


def generate_measurement_report(
    measurements_with_ci: Dict[str, Dict[str, float]],
    quality_reports: Dict[str, MeasurementQuality],
    ethnic_profile: str = "Caucasian"
) -> Dict[str, Any]:
    """
    Generate comprehensive measurement quality report.
    """
    high_confidence = sum(1 for q in quality_reports.values() if q.confidence_level == "high")
    medium_confidence = sum(1 for q in quality_reports.values() if q.confidence_level == "medium")
    low_confidence = sum(1 for q in quality_reports.values() if q.confidence_level == "low")
    
    outliers = [q for q in quality_reports.values() if q.is_outlier]
    with_warnings = [q for q in quality_reports.values() if q.validation_warnings]
    
    # Calculate base precision score (0-100) from confidence distribution
    base_precision = (
        (high_confidence * 3 + medium_confidence * 2 + low_confidence * 1) /
        (len(quality_reports) * 3) * 100
    ) if quality_reports else 0.0

    # Penalize for statistical outliers and anatomical/relationship warning flags
    outlier_penalty = len(outliers) * 15.0      # -15% penalty per statistical outlier
    warning_penalty = len(with_warnings) * 4.0  # -4% penalty per measurement warning
    overall_score = max(0.0, min(100.0, base_precision - outlier_penalty - warning_penalty))

    return {
        "summary": {
            "total_measurements": len(quality_reports),
            "high_confidence_count": high_confidence,
            "medium_confidence_count": medium_confidence,
            "low_confidence_count": low_confidence,
            "outlier_count": len(outliers),
            "overall_quality_score": overall_score
        },
        "confidence_distribution": {
            "high": high_confidence,
            "medium": medium_confidence,
            "low": low_confidence
        },
        "quality_by_measurement": {
            meas_name: {
                "value": q.value,
                "ci_lower": q.ci_lower,
                "ci_upper": q.ci_upper,
                "confidence": q.confidence_level,
                "z_score": round(q.z_score, 2),
                "percentile": round(q.percentile, 1),
                "is_outlier": q.is_outlier,
                "warnings": q.validation_warnings,
                "refinement_priority": q.refinement_priority
            }
            for meas_name, q in quality_reports.items()
        },
        "issues": {
            "outlier_measurements": [q.measurement_name for q in outliers],
            "measurements_with_warnings": len(with_warnings),
            "high_uncertainty_count": sum(
                1 for q in quality_reports.values() 
                if q.refinement_priority in [1, 2]
            )
        },
        "recommendations": [
            "Refine landmarks" if outliers else "Measurement quality excellent",
            f"Focus on high-priority refinements (priority 1: outliers, priority 2: high uncertainty)" if any(q.refinement_priority > 0 for q in quality_reports.values()) else None
        ]
    }
