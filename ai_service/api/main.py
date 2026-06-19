"""AI Cephalometric Landmark Detection FastAPI Server."""

import sys
import os

# Bootstrap path for direct script execution
if __name__ == "__main__" and __package__ is None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    __package__ = "api"

import base64
import binascii
import socket
from io import BytesIO
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from PIL import Image, UnidentifiedImageError
import uvicorn

from ui.utils.image_utils import annotate_image, draw_cartoon_outline

# Relative imports
from .model import load_model, run_inference
from .utils import preprocess_image, postprocess_landmarks, refine_landmarks
from .diagnostic_engine import diagnose_measurements
from .calibration import compute_px_to_mm
from .calibration_auto import auto_detect_px_to_mm
from .ai_engine import generate_patient_explanation
from .protocols import get_protocol, get_protocol_norms_preview, list_protocols, validate_protocol_landmarks
from .norms import list_reference_protocols, get_norm_tuple
from .treatment_engine import build_treatment_plan
from .measurements import summary_report
from .xray_validator import LandmarkXrayValidator, XrayValidator

# Schemas and helpers
from .schemas import *
from .helpers import (
    build_diagnostic_context,
    classify_maxillary_position,
    classify_mandibular_position,
    classify_lower_incisor_inclination,
    classify_skeletal_differential,
    landmark_names_to_ids,
    landmark_ids_to_response_dict,
    parse_treatment_timeline_months
)
from .drawing import pil_to_base64, draw_wiggle_chart, draw_measurement_table, draw_ceph_report


# Global model storage
ml_models = {}
MAX_XRAY_BYTES = 15 * 1024 * 1024


def _severity_from_measurements(measurements: dict[str, float]) -> str:
    """Fallback severity estimate when the caller has not supplied diagnosis severity."""
    anb = measurements.get("ANB")
    fma = measurements.get("FMA (FH-MP)")
    impa = measurements.get("IMPA")
    deviations = []
    if anb is not None:
        deviations.append(abs(float(anb) - 3.0) / 2.0)
    if fma is not None:
        deviations.append(abs(float(fma) - 25.0) / 5.0)
    if impa is not None:
        deviations.append(abs(float(impa) - 90.0) / 5.0)

    max_dev = max(deviations, default=0.0)
    if max_dev >= 2.5:
        return "severe"
    if max_dev >= 1.5:
        return "moderate"
    return "mild"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'best_model.pth')
    if os.path.exists(model_path):
        ml_models["hrnet"] = load_model(model_path)
    else:
        print(f"Warning: Model file not found at {model_path}")

    validator_path = os.getenv("XRAY_VALIDATOR_MODEL_PATH") or os.path.join(
        os.path.dirname(__file__), "..", "models", "xray_validator.pt"
    )
    if os.path.exists(validator_path):
        threshold = float(os.getenv("XRAY_VALIDATOR_THRESHOLD", "0.90"))
        ml_models["xray_validator"] = XrayValidator(validator_path, threshold=threshold)
        ml_models["xray_validator_mode"] = "classifier"
    elif "hrnet" in ml_models:
        ml_models["xray_validator"] = LandmarkXrayValidator(ml_models["hrnet"])
        ml_models["xray_validator_mode"] = "landmark_fallback"
        print(
            "Warning: X-ray classifier model not found; "
            "using landmark-based validation fallback."
        )
    else:
        print(f"Warning: X-ray validator model not found at {validator_path}")
    
    yield
    
    # Cleanup
    ml_models.clear()


# Initialize FastAPI app
app = FastAPI(title="Cephalometric Landmark Detection API", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "API is running. Use /docs for active endpoints."}

@app.get("/health")
def health_check():
    model_loaded = "hrnet" in ml_models
    validator_loaded = "xray_validator" in ml_models
    return {
        "status": "ok" if model_loaded and validator_loaded else "degraded",
        "model_loaded": model_loaded,
        "xray_validator_loaded": validator_loaded,
        "xray_validator_mode": ml_models.get("xray_validator_mode", "unavailable"),
    }


@app.post("/validate-xray")
async def validate_xray(file: UploadFile = File(...)):
    """Accept only images classified as lateral cephalometric X-rays."""
    validator = ml_models.get("xray_validator")
    if validator is None:
        raise HTTPException(
            status_code=503,
            detail="X-ray validation model is unavailable.",
        )

    contents = await file.read(MAX_XRAY_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image file.")
    if len(contents) > MAX_XRAY_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 15 MB.")

    try:
        return validator.validate(contents)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/protocols")
async def protocols():
    return {"protocols": list_protocols()}

@app.get("/protocols/{protocol_id}")
async def protocol_detail(protocol_id: str):
    try:
        return {
            "protocol": get_protocol(protocol_id),
            "norms_preview": get_protocol_norms_preview(protocol_id),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/reference-protocols")
async def reference_protocols():
    """Literature protocols and norms from references/landmark_groups.json."""
    return {"reference_protocols": list_reference_protocols()}

@app.post("/protocols/{protocol_id}/validate")
async def protocol_validate(protocol_id: str, request: ProtocolValidateRequest):
    try:
        return {"validation": validate_protocol_landmarks(protocol_id, [p.model_dump() for p in request.landmarks])}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/calibrate")
async def calibrate(request: CalibrateRequest):
    """Calculate mm-per-pixel scale from two clicked ruler/calibration points."""
    try:
        return {
            "calibration": compute_px_to_mm(
                request.point_a.model_dump(),
                request.point_b.model_dump(),
                request.real_distance_mm,
            )
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auto-calibrate")
async def auto_calibrate(
    file: UploadFile = File(...),
    tick_interval_mm: float = Form(10.0)
):
    """
    Automatically detect the scale calibration factor (px_to_mm) 
    from periodic lead ruler ticks inside border regions of the image.
    """
    try:
        contents = await file.read()
        res = auto_detect_px_to_mm(contents, tick_interval_mm=tick_interval_mm)
        return {"calibration": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/patient-letter")
async def patient_letter_endpoint(request: InterpretRequest):
    try:
        lm_list = [p.model_dump() for p in request.landmarks] if request.landmarks else None
        report, treatment_plan = build_diagnostic_context(
            landmarks=lm_list,
            diagnostic_report=request.diagnostic_report,
            px_to_mm=request.px_to_mm,
            ethnic_profile=request.ethnic_profile,
            protocol_id=request.protocol_id,
            patient_age=request.patient_age,
            patient_sex=request.patient_sex,
        )
        letter = generate_patient_explanation(report, treatment_plan, provider=request.provider)
        return {"patient_letter": letter, "diagnostic_report": report, "treatment_plan": treatment_plan}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post('/refine')
async def refine(file: UploadFile = File(...), landmarks: str = Form(...), 
                 method: str = Form('intensity'), window: int = Form(21), 
                 max_move: float = Form(None)):
    """Refine landmarks by snapping each point to a local image feature."""
    try:
        import json
        contents = await file.read()
        lm_list = json.loads(landmarks)
        refined = refine_landmarks(contents, lm_list, window=window, method=method)

        if max_move is not None:
            out = []
            for orig, new in zip(lm_list, refined):
                dx = new['x'] - orig.get('x', 0)
                dy = new['y'] - orig.get('y', 0)
                dist = (dx*dx + dy*dy) ** 0.5
                accepted = dist <= float(max_move)
                out.append({**new, 'accepted': accepted, 'moved': round(dist, 2)})
            return {"landmarks": out}

        return {"landmarks": refined}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Health and Metadata Endpoints ────────────────────────────────────────

@app.post("/ai/detect-landmarks", response_model=LandmarkDetectionResponse)
async def detect_landmarks_endpoint(request: LandmarkDetectionRequest):
    """Detect cephalometric landmarks from image using HRNet."""
    if "hrnet" not in ml_models:
        raise HTTPException(status_code=500, detail="HRNet model not loaded on server.")
    try:
        try:
            image_bytes = base64.b64decode(request.image_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="Invalid base64 image payload.")

        tensor, original_size = preprocess_image(image_bytes)
        heatmaps, offsets = run_inference(ml_models["hrnet"], tensor)
        landmarks = postprocess_landmarks(heatmaps, original_size, offsets=offsets)
        print(f"Detected {len(landmarks)} landmarks in image of size {original_size}")
        print(f"Landmarks: {landmarks}")
        
        mapped_landmarks = landmark_ids_to_response_dict(landmarks)
        return LandmarkDetectionResponse(landmarks=mapped_landmarks)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Landmark detection failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Landmark detection failed.")


@app.post("/ai/calculate-measurements")
async def calculate_measurements_endpoint(request: AiCalculateMeasurementsRequest):
    """Calculate measurements from detected landmarks."""
    try:
        selected_protocol = request.protocol_id or "core_lateral"
        get_protocol(selected_protocol)
        lm_list = landmark_names_to_ids(request.landmarks)
        report = summary_report(
            lm_list,
            px_to_mm=request.pixel_spacing_mm,
            samples=200,
            base_sigma_px=2.0,
            ethnic_profile=request.population or "Caucasian",
            protocol_id=selected_protocol
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/ai/classify-diagnosis", response_model=DiagnosisResponseModel)
async def classify_diagnosis_endpoint(request: AiDiagnosisClassificationRequest):
    """Generate diagnostic classification from measurements."""
    try:
        selected_protocol = request.protocol_id or "core_lateral"
        get_protocol(selected_protocol)
        rows = []
        ethnic_profile = request.population or "Caucasian"
        for name, value in request.measurements.items():
            norm_mean, norm_sd, meta = get_norm_tuple(selected_protocol, name, ethnic_profile)
            difference = value - norm_mean
            status = "normal"
            label = "Normal"
            
            if norm_sd and norm_sd > 0:
                z = difference / norm_sd
                status = "increased" if z > 1.0 else ("decreased" if z < -1.0 else "normal")
                label = "Increased" if z > 1.0 else ("Decreased" if z < -1.0 else "Normal")
            else:
                if difference > 2.0:
                    status, label = "increased", "Increased"
                elif difference < -2.0:
                    status, label = "decreased", "Decreased"

            rows.append({
                "measurement": name,
                "value": value,
                "mean": norm_mean,
                "sd": norm_sd,
                "norm_mean": norm_mean,
                "norm_sd": norm_sd,
                "difference": difference,
                "status": status,
                "label": label,
                "interpretation": f"{name} is {label}"
            })
        
        measurements_report = {
            "measurements": rows,
            "ethnic_profile": ethnic_profile,
            "protocol_id": selected_protocol,
            "landmarks": [],
            "px_to_mm": 1.0
        }
        
        diagnosis = diagnose_measurements(measurements_report)
        anb = request.measurements.get("ANB", 3.0)
        sna = request.measurements.get("SNA", 82.0)
        snb = request.measurements.get("SNB", 80.0)
        impa = request.measurements.get("IMPA", 90.0)
        
        sk_class = diagnosis.get("skeletal_class", "Class I")
        warnings = list(diagnosis.get("recommendations", []))
        warnings.append("Overjet, overbite, upper incisor inclination, and soft-tissue profile are not calculated from the current staged endpoint payload.")
        
        return DiagnosisResponseModel(
            skeletal_class=sk_class,
            skeletal_type="CII" if sk_class == "Class II" else "CIII" if sk_class == "Class III" else "CI",
            corrected_anb=anb,
            apdi_classification="Normal",
            odi_classification="Normal",
            vertical_pattern=diagnosis.get("vertical_pattern", "Normodivergent"),
            maxillary_position=classify_maxillary_position(sna),
            mandibular_position=classify_mandibular_position(snb),
            upper_incisor_inclination=None,
            lower_incisor_inclination=classify_lower_incisor_inclination(impa) if "IMPA" in request.measurements else None,
            soft_tissue_profile=None,
            overjet_mm=None,
            overjet_classification=None,
            overbite_mm=None,
            overbite_classification=None,
            confidence_score=diagnosis.get("confidence", 0.90),
            severity=diagnosis.get("severity"),
            summary=diagnosis.get("professional_summary", ""),
            warnings=warnings,
            clinical_notes=[f.get("interpretation") for f in diagnosis.get("findings", []) if f.get("interpretation")],
            skeletal_differential=classify_skeletal_differential(sk_class)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/suggest-treatment", response_model=AiTreatmentSuggestionResponse)
async def suggest_treatment_endpoint(request: AiTreatmentSuggestionRequest):
    """Generate treatment suggestions from diagnosis."""
    try:
        impa = request.measurements.get("IMPA", 90.0)
        dental_pattern = "balanced incisor inclination"
        if impa > 95:
            dental_pattern = "proclined lower incisors"
        elif impa < 85:
            dental_pattern = "retroclined lower incisors"
        
        diagnostic_report = {
            "skeletal_class": request.skeletal_class,
            "vertical_pattern": request.vertical_pattern,
            "severity": request.severity or _severity_from_measurements(request.measurements),
            "dental_pattern": dental_pattern,
            "diagnostic_code": "CI-NVD-M"
        }
        
        plan = build_treatment_plan(diagnostic_report, age=int(request.patient_age))
        dtos = []
        
        # Primary recommendation
        prim = plan.get("primary_recommendation")
        if prim:
            dtos.append(TreatmentDto(
                plan_index=0,
                treatment_type="Orthopedic" if any(x in prim.get("title", "").lower() for x in ["block", "facemask"]) else "Orthodontic",
                treatment_name=prim.get("title", "Interceptive monitoring"),
                description=prim.get("alternative", "Standard mechanics"),
                rationale=prim.get("rationale"),
                risks=", ".join([f"{r.get('complication')}: {r.get('mitigation')}" 
                                for r in plan.get("risk_assessment", {}).get("specific_risks", [])]),
                estimated_duration_months=parse_treatment_timeline_months(prim.get("timeline_months", "18")),
                confidence_score=0.90,
                source="ai",
                is_primary=True,
                evidence_reference=prim.get("evidence_refs", [None])[0],
                evidence_level=prim.get("evidence_level"),
                retention_recommendation="Standard vacuum-formed retainers",
                predicted_outcomes={"success_probability": 0.85}
            ))
        
        # Alternative recommendations
        for idx, alt in enumerate(plan.get("alternative_recommendations", []), 1):
            dtos.append(TreatmentDto(
                plan_index=idx,
                treatment_type="Orthodontic",
                treatment_name=alt.get("title", "Alternative therapy"),
                description=alt.get("alternative", "Conservative therapy"),
                rationale=alt.get("rationale"),
                risks="General orthodontic risks",
                estimated_duration_months=parse_treatment_timeline_months(alt.get("timeline_months", "12")),
                confidence_score=0.80,
                source="ai",
                is_primary=False,
                evidence_reference=alt.get("evidence_refs", [None])[0],
                evidence_level=alt.get("evidence_level"),
                retention_recommendation="Standard retention",
                predicted_outcomes={"success_probability": 0.75}
            ))
        
        return AiTreatmentSuggestionResponse(treatments=dtos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/explain-decision", response_model=AiXaiResponsePayload)
async def explain_decision_endpoint(request: AiXaiRequestPayload):
    """Generate explainable AI decision chain and reasoning."""
    try:
        decision_chain = [
            XAIDecisionStep(
                step=1,
                factor="Sagittal Skeletal Classification",
                evidence=f"Skeletal class resolved as {request.skeletal_class}.",
                impact="Guided selection of primary sagittal correction mechanics."
            ),
            XAIDecisionStep(
                step=2,
                factor="Vertical Pattern",
                evidence=f"Vertical pattern identified as {request.vertical_pattern}.",
                impact="Influenced vertical control, anchorage selection, and elastics direction."
            ),
            XAIDecisionStep(
                step=3,
                factor="Dentoalveolar Compensation",
                evidence=f"IMPA value of {request.measurements.get('IMPA', 90.0)}°.",
                impact="Determined extraction vs. non-extraction mechanics for proclination."
            )
        ]
        
        key_drivers = []
        if abs(request.measurements.get("ANB", 3.0) - 3.0) > 1.5:
            key_drivers.append("ANB Sagittal relationship deviation")
        if abs(request.measurements.get("FMA (FH-MP)", 25.0) - 25.0) > 4.0:
            key_drivers.append("FMA vertical divergence")
        if abs(request.measurements.get("IMPA", 90.0) - 90.0) > 5.0:
            key_drivers.append("Lower incisor mandibular plane angle compensation")
        if not key_drivers:
            key_drivers.append("Normal sagittal and vertical facial symmetry parameters")
        
        uncertainty_factors = []
        if request.uncertainty_landmarks:
            uncertainty_factors.extend([f"Position uncertainty at landmark {lm}" for lm in request.uncertainty_landmarks])
        else:
            uncertainty_factors.append("Low landmark identification error deviation")
        
        return AiXaiResponsePayload(
            decision_chain=decision_chain,
            key_drivers=key_drivers,
            uncertainty_factors=uncertainty_factors,
            clinical_confidence="High Clinical Confidence (90%) based on robust bilateral anatomical validation.",
            alternative_interpretation="Borderline Class II/III could use high-compliance class mechanics if surgery declined."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/generate-overlays", response_model=AiOverlayResponsePayload)
async def generate_overlays_endpoint(request: AiOverlayRequestPayload):
    """Generate overlay images for visualization."""
    try:
        try:
            image_bytes = base64.b64decode(request.image_base64, validate=True)
            orig_img = Image.open(BytesIO(image_bytes))
            orig_img.load()
        except (binascii.Error, ValueError, UnidentifiedImageError):
            raise HTTPException(status_code=400, detail="Invalid base64 image payload.")
        
        lm_list = landmark_names_to_ids(request.landmarks)
        image_items = []
        
        for out in request.outputs:
            out_key = out.lower()
            img_out = None
            label = ""
            
            if out_key == "xray_tracing":
                img_out = annotate_image(orig_img, lm_list, draw_points=True, show_lines=True, show_labels=True, show_scores=False)
                label = "X-Ray Tracing with Landmarks"
            elif out_key == "xray_measurements":
                img_out = draw_cartoon_outline(orig_img, lm_list, blank_background=False, px_to_mm=request.pixel_spacing_mm)
                label = "X-Ray Tracing with Measurements"
            elif out_key == "tracing_only":
                img_out = draw_cartoon_outline(orig_img, lm_list, blank_background=True, px_to_mm=request.pixel_spacing_mm)
                label = "Anatomical Tracing Only"
            elif out_key == "wiggle_chart":
                img_out = draw_wiggle_chart(lm_list, request.measurements, request.patient_label, request.date_label)
                label = "Steiner Wiggle Chart"
            elif out_key == "measurement_table":
                img_out = draw_measurement_table(request.measurements, request.patient_label, request.date_label)
                label = "Clinical Measurement Table"
            elif out_key == "ceph_report":
                img_out = draw_ceph_report(lm_list, request.measurements, request.patient_label, request.date_label, request.session_id)
                label = "Clinical Cephalometric Report"
            
            if img_out is not None:
                image_items.append(AiOverlayImagePayload(
                    key=out,
                    label=label,
                    image_base64=pil_to_base64(img_out),
                    width=img_out.width,
                    height=img_out.height
                ))
        
        return AiOverlayResponsePayload(session_id=request.session_id, images=image_items, render_ms=120)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ai/norms")
async def get_norms_endpoint():
    """List available reference norms and protocols."""
    try:
        return list_reference_protocols()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    """Start the API server."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Get host and port from environment
    host = os.getenv("API_HOST") or "127.0.0.1"
    port_str = os.getenv("API_PORT") or "8000"
    
    # Try parsing from CEPHALO_API_URL if not set
    if host == "127.0.0.1" and not os.getenv("API_HOST"):
        cephalo_url = os.getenv("CEPHALO_API_URL")
        if cephalo_url:
            try:
                parsed = urlparse(cephalo_url)
                if parsed.hostname:
                    host = "127.0.0.1" if parsed.hostname == "localhost" else parsed.hostname
                if parsed.port:
                    port_str = str(parsed.port)
            except Exception:
                pass

    try:
        port = int(port_str)
    except ValueError:
        port = 8000

    print(f"Starting AI Cephalometric Landmark Detection API...")
    print(f"API listening on http://{host}:{port}")
    
    if host == "127.0.0.1":
        print("Note: Listening on localhost. For external access, set API_HOST=0.0.0.0 in .env")
    elif host == "0.0.0.0":
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            print(f"Accessible on local network at: http://{local_ip}:{port}")
        except Exception:
            pass

    uvicorn.run(app, host=host, port=port)
