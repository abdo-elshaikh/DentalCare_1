"""Growth Stage Detection Module - Phase 3.1

Cervical Vertebral Maturation (CVM) stage detection and growth potential estimation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class GrowthStageResult:
    """Growth stage assessment result."""
    cvm_stage: int  # 1-6 (Lamprey-Franchi scale)
    stage_name: str  # Detailed stage description
    growth_remaining_estimate: str  # "high", "moderate", "low", "minimal"
    remaining_months: Tuple[int, int]  # (min, max) months of growth expected
    optimal_treatment_window: str  # Recommendation
    treatment_timing_score: float  # 0-1 where 1 is optimal timing


# CVM Stage reference - based on cervical vertebral morphology
CVM_STAGES = {
    1: {
        "name": "Stage 1 - Pre-pubertal",
        "description": "All vertebrae have flat or slightly concave lower borders. No concavity in C2, C3, or C4",
        "growth_potential": "high",
        "expected_growth_months": (36, 60),
        "dental_stage": "Primary or early mixed dentition"
    },
    2: {
        "name": "Stage 2 - Pubertal",
        "description": "Concavity at lower border of C2, or C3, or C4 becomes evident",
        "growth_potential": "high",
        "expected_growth_months": (24, 48),
        "dental_stage": "Mixed dentition"
    },
    3: {
        "name": "Stage 3 - Pubertal",
        "description": "Concavity extends through entire lower border of C2, C3, and C4. Vertebrae begin to elongate",
        "growth_potential": "moderate",
        "expected_growth_months": (12, 24),
        "dental_stage": "Mixed/early permanent dentition"
    },
    4: {
        "name": "Stage 4 - Post-pubertal",
        "description": "C3 and/or C4 become more rectangular (height > width). Lower borders still concave",
        "growth_potential": "moderate",
        "expected_growth_months": (6, 12),
        "dental_stage": "Permanent dentition"
    },
    5: {
        "name": "Stage 5 - Post-pubertal",
        "description": "C3 and C4 now nearly square (height ~ width) or longer than wide",
        "growth_potential": "low",
        "expected_growth_months": (3, 6),
        "dental_stage": "Permanent dentition established"
    },
    6: {
        "name": "Stage 6 - Completion",
        "description": "C3 and/or C4 become taller than wide, lower borders straight",
        "growth_potential": "minimal",
        "expected_growth_months": (0, 3),
        "dental_stage": "Complete permanent dentition"
    }
}


def estimate_cvm_stage_from_morphology(
    landmarks: List[Dict[str, Any]],
    px_to_mm: float = 1.0
) -> Optional[int]:
    """
    Estimate cervical vertebral maturation stage from landmark morphology.
    
    Looks for specific vertebral characteristics in cervical vertebrae region (C2, C3, C4).
    Returns CVM stage (1-6) or None if insufficient data.
    """
    # 1. Helper to find a coordinate by symbol, ID, title, name, or code
    def get_coord(query_name: str) -> Optional[Tuple[float, float]]:
        q = "".join(c for c in query_name.lower() if c.isalnum())
        for lm in landmarks:
            for key in ["id", "symbol", "title", "name", "code"]:
                val = lm.get(key)
                if val is not None:
                    val_str = "".join(c for c in str(val).lower() if c.isalnum())
                    if q == val_str:
                        return (float(lm["x"]), float(lm["y"]))
        return None

    # 2. Extract C2 landmarks (inferior-posterior, inferior-anterior, inferior-midpoint)
    c2_ip = get_coord("C2_IP") or get_coord("C2ip") or get_coord("C2 Inferior Posterior")
    c2_ia = get_coord("C2_IA") or get_coord("C2ia") or get_coord("C2 Inferior Anterior")
    c2_i = get_coord("C2_I") or get_coord("C2i") or get_coord("C2 Inferior Midpoint") or get_coord("C2 Inferior")

    # Extract C3 landmarks
    c3_sp = get_coord("C3_SP") or get_coord("C3sp") or get_coord("C3 Superior Posterior")
    c3_sa = get_coord("C3_SA") or get_coord("C3sa") or get_coord("C3 Superior Anterior")
    c3_ip = get_coord("C3_IP") or get_coord("C3ip") or get_coord("C3 Inferior Posterior")
    c3_ia = get_coord("C3_IA") or get_coord("C3ia") or get_coord("C3 Inferior Anterior")
    c3_i = get_coord("C3_I") or get_coord("C3i") or get_coord("C3 Inferior Midpoint") or get_coord("C3 Inferior")

    # Extract C4 landmarks
    c4_sp = get_coord("C4_SP") or get_coord("C4sp") or get_coord("C4 Superior Posterior")
    c4_sa = get_coord("C4_SA") or get_coord("C4sa") or get_coord("C4 Superior Anterior")
    c4_ip = get_coord("C4_IP") or get_coord("C4ip") or get_coord("C4 Inferior Posterior")
    c4_ia = get_coord("C4_IA") or get_coord("C4ia") or get_coord("C4 Inferior Anterior")
    c4_i = get_coord("C4_I") or get_coord("C4i") or get_coord("C4 Inferior Midpoint") or get_coord("C4 Inferior")

    # If key landmarks are missing, we cannot perform morphological estimation.
    if not (c2_ip and c2_ia and c2_i and
            c3_sp and c3_sa and c3_ip and c3_ia and c3_i and
            c4_sp and c4_sa and c4_ip and c4_ia and c4_i):
        return None

    # Helper function to compute Euclidean distance
    def dist(p1, p2):
        return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5

    # Helper to calculate lower border concavity depth in mm
    def compute_concavity_depth(ip, ia, i_pt) -> float:
        # Midpoint of the line connecting inferior corners
        mid_x = (ip[0] + ia[0]) / 2.0
        mid_y = (ip[1] + ia[1]) / 2.0
        
        # In lateral ceph image coordinates, y increases downward.
        # Concavity means the midpoint curves superiorly (upward),
        # so the y-coordinate of the midpoint i_pt should be smaller than mid_y.
        is_curved_up = i_pt[1] < mid_y
        if not is_curved_up:
            return 0.0
            
        # Perpendicular distance from i_pt to the line connecting ip and ia
        # Line equation: A*x + B*y + C = 0
        # A = y2 - y1, B = x1 - x2, C = x2*y1 - x1*y2
        a = ia[1] - ip[1]
        b = ip[0] - ia[0]
        c = ia[0] * ip[1] - ip[0] * ia[1]
        
        denom = (a**2 + b**2)**0.5
        if denom == 0:
            return 0.0
            
        pixel_depth = abs(a * i_pt[0] + b * i_pt[1] + c) / denom
        return pixel_depth * px_to_mm

    # Helper to classify C3/C4 shape based on height-to-width ratio
    def get_shape_class(sp, sa, ip, ia) -> str:
        # width = inferior width
        w = dist(ip, ia)
        # height = average of posterior and anterior vertical heights
        h = (dist(sp, ip) + dist(sa, ia)) / 2.0
        if w == 0:
            return "horizontal"
        
        ratio = h / w
        if ratio < 0.90:
            return "horizontal"
        elif ratio <= 1.15:
            return "square"
        else:
            return "vertical"

    # 3. Calculate concavities (presence defined as depth >= 1.0 mm)
    c2_depth = compute_concavity_depth(c2_ip, c2_ia, c2_i)
    c3_depth = compute_concavity_depth(c3_ip, c3_ia, c3_i)
    c4_depth = compute_concavity_depth(c4_ip, c4_ia, c4_i)
    
    c2_concave = c2_depth >= 1.0
    c3_concave = c3_depth >= 1.0
    c4_concave = c4_depth >= 1.0

    # Classify C3 and C4 body shapes
    c3_shape = get_shape_class(c3_sp, c3_sa, c3_ip, c3_ia)
    c4_shape = get_shape_class(c4_sp, c4_sa, c4_ip, c4_ia)

    # 4. Apply Franchi-Baccetti CVM stage rules
    if not c2_concave:
        # Stage 1: All lower borders flat.
        return 1
        
    if c2_concave and not c3_concave:
        # Stage 2: Concavity only on C2 lower border.
        return 2
        
    if c2_concave and c3_concave and not c4_concave:
        # Stage 3: Concavities on C2 and C3; C4 is flat.
        return 3

    # If all three lower borders are concave (Stage 4, 5, or 6):
    if c2_concave and c3_concave and c4_concave:
        if c3_shape == "horizontal" and c4_shape == "horizontal":
            # Stage 4: Concave borders; C3/C4 horizontal rectangular.
            return 4
        elif c3_shape == "vertical" or c4_shape == "vertical":
            # Stage 6: Concave borders; C3 and/or C4 vertical rectangular.
            return 6
        else:
            # Stage 5: Concave borders; C3 and/or C4 square.
            return 5

    # Fallbacks
    if c2_concave and c3_concave and c4_concave:
        return 4
    elif c2_concave and c3_concave:
        return 3
    elif c2_concave:
        return 2
    else:
        return 1


def estimate_cvm_stage_from_age_sex(
    age: Optional[int] = None,
    sex: Optional[str] = None
) -> Tuple[int, float]:
    """
    Estimate CVM stage from age and sex using population averages.
    
    Returns (estimated_stage, confidence) where confidence is 0-1.
    Lower confidence = higher variance in population at that age.
    """
    if age is None:
        return 3, 0.4  # Middle stage, low confidence
    
    # Approximate age ranges for CVM stages
    # Based on Lamprey-Franchi studies
    # These are medians - actual variance is high
    
    if sex == "female":
        if age < 9:
            return 1, 0.3
        elif age < 10:
            return 2, 0.4
        elif age < 11:
            return 2, 0.5
        elif age < 12:
            return 3, 0.5
        elif age < 13:
            return 3, 0.5
        elif age < 14:
            return 4, 0.5
        elif age < 15:
            return 4, 0.4
        elif age < 16:
            return 5, 0.4
        elif age < 17:
            return 5, 0.3
        else:
            return 6, 0.2
    
    elif sex == "male":
        if age < 10:
            return 1, 0.3
        elif age < 11:
            return 2, 0.4
        elif age < 12:
            return 2, 0.5
        elif age < 13:
            return 2, 0.5
        elif age < 14:
            return 3, 0.5
        elif age < 15:
            return 3, 0.5
        elif age < 16:
            return 4, 0.5
        elif age < 17:
            return 4, 0.4
        elif age < 18:
            return 5, 0.3
        else:
            return 6, 0.2
    
    else:
        # Unknown sex - use average
        if age < 10:
            return 1, 0.3
        elif age < 12:
            return 2, 0.4
        elif age < 14:
            return 3, 0.5
        elif age < 16:
            return 4, 0.45
        elif age < 17:
            return 5, 0.35
        else:
            return 6, 0.2


def estimate_growth_potential(
    cvm_stage: int,
    age: Optional[int] = None,
    sex: Optional[str] = None
) -> GrowthStageResult:
    """
    Estimate remaining growth potential based on CVM stage.
    
    Combines CVM stage (most reliable) with age/sex for refinement.
    """
    if cvm_stage < 1 or cvm_stage > 6:
        cvm_stage = 3  # Default to middle stage if invalid
    
    stage_info = CVM_STAGES.get(cvm_stage, CVM_STAGES[3])
    growth_potential = stage_info["growth_potential"]
    expected_months = stage_info["expected_growth_months"]
    
    # Refine estimate based on age/sex if available
    if age is not None:
        if age >= 18:
            growth_potential = "minimal"
            expected_months = (0, 3)
        elif age >= 17:
            if growth_potential != "minimal":
                growth_potential = "low"
                expected_months = (3, 6)
        elif age >= 16:
            if growth_potential == "high":
                growth_potential = "moderate"
    
    # Determine treatment timing
    if growth_potential == "high":
        treatment_timing = (
            "OPTIMAL NOW: Patient is in active growth phase. "
            "Consider interceptive or orthopedic treatment to guide growth."
        )
        timing_score = 0.95
    elif growth_potential == "moderate":
        treatment_timing = (
            "Good timing: Significant growth potential remains. "
            "Proceed with planned treatment to harness residual growth."
        )
        timing_score = 0.80
    elif growth_potential == "low":
        treatment_timing = (
            "Limited growth: Minimal growth potential. "
            "Focus on camouflage or consider surgical options if severe."
        )
        timing_score = 0.50
    else:  # minimal
        treatment_timing = (
            "Growth complete: No significant growth expected. "
            "Orthognathic surgery may be indicated for severe discrepancies."
        )
        timing_score = 0.30
    
    return GrowthStageResult(
        cvm_stage=cvm_stage,
        stage_name=stage_info["name"],
        growth_remaining_estimate=growth_potential,
        remaining_months=expected_months,
        optimal_treatment_window=treatment_timing,
        treatment_timing_score=timing_score
    )


def predict_treatment_timing(
    age: Optional[int] = None,
    sex: Optional[str] = None,
    cvm_stage: Optional[int] = None
) -> Dict[str, Any]:
    """
    Predict optimal treatment timing and expected growth trajectory.
    """
    # Determine CVM stage if not provided
    if cvm_stage is None:
        cvm_stage, _ = estimate_cvm_stage_from_age_sex(age, sex)
    
    # Get growth potential
    growth_result = estimate_growth_potential(cvm_stage, age, sex)
    
    # Calculate treatment phases
    is_growing = growth_result.growth_remaining_estimate in ["high", "moderate"]
    
    phases = []
    if is_growing:
        phases.append({
            "name": "Pre-treatment assessment",
            "duration_months": 1,
            "description": "Document baseline, assess growth pattern"
        })
        phases.append({
            "name": "Growth guidance phase",
            "duration_months": growth_result.remaining_months[0],
            "description": "Use appliances to guide natural growth",
            "critical": True
        })
        if age and age < 13:
            phases.append({
                "name": "Correction phase",
                "duration_months": 12,
                "description": "Fixed appliances for final correction"
            })
    else:
        phases.append({
            "name": "Comprehensive treatment",
            "duration_months": 24,
            "description": "Fixed appliance therapy without growth guidance"
        })
    
    phases.append({
        "name": "Retention",
        "duration_months": 36,
        "description": "Long-term stability maintenance"
    })
    
    return {
        "cvm_stage": growth_result.cvm_stage,
        "stage_name": growth_result.stage_name,
        "growth_remaining": growth_result.growth_remaining_estimate,
        "remaining_growth_months": growth_result.remaining_months,
        "is_growing": is_growing,
        "treatment_timing": growth_result.optimal_treatment_window,
        "treatment_timing_score": growth_result.treatment_timing_score,
        "treatment_phases": phases,
        "total_treatment_months": sum(p["duration_months"] for p in phases),
        "recommendations": [
            "Assess growth pattern before starting treatment",
            "If growing: prioritize growth guidance over camouflage",
            "If growth complete: consider orthognathic surgery if severe",
            "Monitor compliance throughout treatment",
            "Long-term retention critical for stability"
        ]
    }


def calculate_growth_vector_prediction(
    age: Optional[int] = None,
    sex: Optional[str] = None,
    current_measurements: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Predict growth direction and magnitude using population vectors.
    """
    cvm_stage, confidence = estimate_cvm_stage_from_age_sex(age, sex)
    growth_potential = estimate_growth_potential(cvm_stage, age, sex)
    
    is_growing = growth_potential.growth_remaining_estimate in ["high", "moderate"]
    
    if not is_growing:
        return {
            "growth_potential": "minimal",
            "expected_changes": {},
            "prediction_confidence": 0.8
        }
    
    # Typical growth vectors by age and sex
    # These are population averages from longitudinal studies
    
    sex_type = sex or "average"
    age_group = age or 12
    
    # Approximate expected changes per year
    growth_changes = {
        "ANB_change_per_year": -0.1,  # Slight decrease (mandibular growth)
        "FMA_increase_per_year": 0.5,  # Slight increase (vertical growth)
        "SN_GoGn_increase_per_year": 0.8,  # Mandibular plane increases
        "Lower_anterior_height_increase_per_year": 1.2,  # Vertical increase
    }
    
    remaining_years = growth_potential.remaining_months[0] / 12.0
    
    expected_changes = {
        k: v * remaining_years
        for k, v in growth_changes.items()
    }
    
    return {
        "cvm_stage": cvm_stage,
        "stage_name": growth_potential.stage_name,
        "growth_potential": growth_potential.growth_remaining_estimate,
        "remaining_growth_period_months": growth_potential.remaining_months,
        "expected_changes_per_month": {
            k: v / 12.0
            for k, v in growth_changes.items()
        },
        "expected_total_changes": expected_changes,
        "prediction_confidence": confidence,
        "note": "Based on population averages. Individual variation is high."
    }


def generate_growth_report(
    age: Optional[int] = None,
    sex: Optional[str] = None,
    cvm_stage: Optional[int] = None,
    landmarks: Optional[List[Dict[str, Any]]] = None,
    px_to_mm: float = 1.0
) -> Dict[str, Any]:
    """
    Generate comprehensive growth and maturation assessment.
    """
    # Try to detect CVM from landmarks if available
    if cvm_stage is None and landmarks:
        detected_stage = estimate_cvm_stage_from_morphology(landmarks, px_to_mm)
        if detected_stage:
            cvm_stage = detected_stage
    
    # Estimate from age/sex if CVM not available
    if cvm_stage is None:
        cvm_stage, age_confidence = estimate_cvm_stage_from_age_sex(age, sex)
    else:
        age_confidence = 0.7  # Moderate confidence when stage is observed
    
    # Get growth potential
    growth_result = estimate_growth_potential(cvm_stage, age, sex)
    
    # Get treatment timing
    treatment_timing = predict_treatment_timing(age, sex, cvm_stage)
    
    # Get growth vector
    growth_vector = calculate_growth_vector_prediction(age, sex)
    
    return {
        "assessment_summary": {
            "cvm_stage": cvm_stage,
            "stage_name": growth_result.stage_name,
            "assessment_confidence": age_confidence,
            "age_sex": f"{age or 'unknown'} y/o {sex or 'unknown'}"
        },
        "growth_potential": {
            "classification": growth_result.growth_remaining_estimate,
            "remaining_months": growth_result.remaining_months,
            "is_actively_growing": growth_result.growth_remaining_estimate in ["high", "moderate"]
        },
        "treatment_timing": {
            "recommendation": growth_result.optimal_treatment_window,
            "optimality_score": growth_result.treatment_timing_score,
            "phases": treatment_timing["treatment_phases"],
            "total_duration_months": treatment_timing["total_treatment_months"]
        },
        "growth_projection": growth_vector,
        "clinical_implications": [
            "Assessment of growth status guides treatment modality selection",
            "Growing patients: prioritize orthopedic/interceptive treatment",
            "Non-growing patients: focus on camouflage or surgical correction",
            "Baseline maturation status critical for predicting treatment duration",
            "Consider growth in setting treatment goals and retention protocols"
        ],
        "limitations": [
            "Age/sex estimates have high population variance",
            "CVM stage from morphology requires full cervical spine radiograph",
            "Individual growth patterns vary significantly",
            "Growth prediction improves with serial radiographs",
            "Clinical judgment essential for final treatment planning"
        ]
    }
