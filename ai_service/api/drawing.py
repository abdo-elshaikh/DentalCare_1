"""Image drawing and overlay utilities."""

import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Any, Optional


def pil_to_base64(img: Image.Image) -> str:
    """Convert PIL image to base64-encoded PNG string."""
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def _get_fonts(title_size=20, section_size=16, bold_size=12, body_size=11):
    """Load fonts with fallback to default."""
    try:
        title_font = ImageFont.truetype("arial.ttf", title_size)
        section_font = ImageFont.truetype("arial.ttf", section_size)
        bold_font = ImageFont.truetype("arial.ttf", bold_size)
        body_font = ImageFont.truetype("arial.ttf", body_size - 1)
        label_font = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        title_font = section_font = bold_font = body_font = label_font = ImageFont.load_default()
    
    return title_font, section_font, bold_font, body_font, label_font


def draw_wiggle_chart(landmarks: List[Dict[str, Any]], measurements: List[Any], 
                      patient_label: Optional[str], date_label: Optional[str]) -> Image.Image:
    """Generate a Steiner Wiggle Chart overlay."""
    img = Image.new("RGB", (600, 500), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    _, _, _, _, label_font = _get_fonts(16, 11)
    title_font = label_font
    
    draw.text((20, 20), "STEINER WIGGLE CHART", fill=(15, 23, 42), font=title_font)
    draw.text((20, 45), f"Patient: {patient_label or 'N/A'}  |  Date: {date_label or 'N/A'}", 
              fill=(100, 116, 139), font=label_font)
    
    # Draw grid
    center_x = 350
    draw.line([(center_x, 80), (center_x, 460)], fill=(148, 163, 184), width=2)
    draw.rectangle([250, 80, 450, 460], fill=(224, 242, 254))
    draw.line([(250, 80), (250, 460)], fill=(186, 230, 253), width=1)
    draw.line([(450, 80), (450, 460)], fill=(186, 230, 253), width=1)
    
    # Headers
    draw.text((30, 75), "Measurement", fill=(15, 23, 42), font=label_font)
    draw.text((245, 60), "-1 SD", fill=(100, 116, 139), font=label_font)
    draw.text((345, 60), "Norm", fill=(15, 23, 42), font=label_font)
    draw.text((445, 60), "+1 SD", fill=(100, 116, 139), font=label_font)
    
    plot_items = ["SNA", "SNB", "ANB", "FMA (FH-MP)", "IMPA", "FMIA", "Nasolabial angle"]
    meas_by_code = {m.code: m for m in measurements}
    
    y = 100
    points_to_connect = []
    for code in plot_items:
        draw.text((30, y), code, fill=(15, 23, 42), font=label_font)
        m = meas_by_code.get(code)
        if m:
            val = m.value
            norm = m.normal_value
            sd = m.std_deviation or 1.5
            diff_sd = (val - norm) / sd if sd > 0 else 0.0
            x = center_x + int(diff_sd * 100)
            x = max(100, min(550, x))
            points_to_connect.append((x, y + 6))
            draw.text((150, y), f"{val:.1f} {m.unit}", fill=(15, 23, 42), font=label_font)
        y += 50
    
    # Connect points
    if len(points_to_connect) > 1:
        draw.line(points_to_connect, fill=(14, 165, 233), width=3)
    for x, y in points_to_connect:
        draw.ellipse([(x-5, y-5), (x+5, y+5)], fill=(2, 132, 199), outline=(255, 255, 255))
    
    return img


def draw_measurement_table(measurements: List[Any], patient_label: Optional[str], 
                          date_label: Optional[str]) -> Image.Image:
    """Generate a measurement table overlay."""
    img = Image.new("RGB", (650, 500), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    _, _, _, body_font, label_font = _get_fonts(16, 12, 11)
    title_font = label_font
    header_font = label_font
    
    # Table header
    draw.rectangle([0, 0, 650, 60], fill=(8, 14, 28))
    draw.text((20, 10), "AI CEPHALOMETRIC MEASUREMENT TABLE", fill=(255, 255, 255), font=title_font)
    draw.text((20, 35), f"Patient: {patient_label or 'N/A'}  |  Date: {date_label or 'N/A'}", 
              fill=(148, 163, 184), font=body_font)
    
    # Column headers
    headers = [("Code", 20), ("Name", 80), ("Value", 300), ("Norm Mean", 400), ("Diff", 500), ("Status", 570)]
    draw.rectangle([0, 60, 650, 90], fill=(241, 245, 249))
    for text, x in headers:
        draw.text((x, 68), text, fill=(15, 23, 42), font=header_font)
    
    y = 95
    for idx, m in enumerate(measurements[:12]):
        bg = (255, 255, 255) if idx % 2 == 0 else (248, 250, 252)
        draw.rectangle([0, y, 650, y + 30], fill=bg)
        
        status_color = (22, 163, 74) if m.status.lower() == "normal" else (220, 38, 38)
        
        draw.text((20, y + 8), m.code, fill=(15, 23, 42), font=body_font)
        name_text = m.name[:30] + "..." if len(m.name) > 33 else m.name
        draw.text((80, y + 8), name_text, fill=(71, 85, 105), font=body_font)
        draw.text((300, y + 8), f"{m.value:.1f} {m.unit}", fill=(15, 23, 42), font=body_font)
        draw.text((400, y + 8), f"{m.normal_value:.1f}", fill=(71, 85, 105), font=body_font)
        
        diff_sign = "+" if m.difference > 0 else ""
        draw.text((500, y + 8), f"{diff_sign}{m.difference:.1f}", fill=(71, 85, 105), font=body_font)
        draw.text((570, y + 8), m.status.upper(), fill=status_color, font=body_font)
        
        y += 30
    
    return img


def draw_ceph_report(landmarks: List[Dict[str, Any]], measurements: List[Any], 
                    patient_label: Optional[str], date_label: Optional[str], 
                    session_id: str) -> Image.Image:
    """Generate a clinical cephalometric report overlay."""
    img = Image.new("RGB", (650, 850), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    title_font, section_font, bold_font, body_font, _ = _get_fonts(20, 14, 11, 10)
    
    # Header
    draw.rectangle([0, 0, 650, 100], fill=(15, 23, 42))
    draw.text((30, 25), "AI CLINICAL CEPHALOMETRIC REPORT", fill=(255, 255, 255), font=title_font)
    draw.text((30, 60), "Digital Orthodontic Analysis System", fill=(148, 163, 184), font=bold_font)
    
    # Metadata
    draw.rectangle([30, 120, 620, 190], fill=(248, 250, 252), outline=(226, 232, 240))
    draw.text((45, 132), f"Patient Name: {patient_label or 'N/A'}", fill=(15, 23, 42), font=bold_font)
    draw.text((45, 152), f"Analysis Date: {date_label or 'N/A'}", fill=(15, 23, 42), font=bold_font)
    draw.text((350, 132), f"Session ID: {session_id}", fill=(71, 85, 105), font=body_font)
    draw.text((350, 152), "Normative Protocol: Lateral Cephalometric Standard", 
              fill=(71, 85, 105), font=body_font)
    draw.text((45, 172), f"Anatomical Landmarks Detected: {len(landmarks)}", 
              fill=(71, 85, 105), font=body_font)
    
    # Diagnosis summary
    draw.text((30, 215), "SKELETAL & DENTAL DIAGNOSIS SUMMARY", fill=(15, 23, 42), font=section_font)
    draw.line([(30, 235), (620, 235)], fill=(15, 23, 42), width=2)
    
    # Classify from measurements
    meas_by_code = {m.code: m.value for m in measurements}
    anb = meas_by_code.get("ANB", 3.0)
    fma = meas_by_code.get("FMA (FH-MP)", 25.0)
    
    skeletal_class = "Class I (Normal sagittal jaw relationship)"
    if anb >= 4.5:
        skeletal_class = "Class II (Maxillary protrusion / Mandibular retrognathism)"
    elif anb <= 1.0:
        skeletal_class = "Class III (Mandibular protrusion / Maxillary retrognathism)"
    
    vertical_pattern = "Normodivergent (Average facial height proportions)"
    if fma > 29.0:
        vertical_pattern = "Hyperdivergent (High angle, increased vertical divergence)"
    elif fma < 21.0:
        vertical_pattern = "Hypodivergent (Low angle, reduced vertical divergence)"
    
    draw.text((45, 250), "Skeletal Sagittal Pattern:", fill=(15, 23, 42), font=bold_font)
    draw.text((220, 250), skeletal_class, fill=(71, 85, 105), font=body_font)
    
    draw.text((45, 275), "Vertical Pattern:", fill=(15, 23, 42), font=bold_font)
    draw.text((220, 275), vertical_pattern, fill=(71, 85, 105), font=body_font)
    
    draw.text((45, 300), "SNA (Maxilla relative to cranial base):", fill=(15, 23, 42), font=bold_font)
    draw.text((350, 300), f"{meas_by_code.get('SNA', 82.0):.1f}° (Norm: 82.0°)", 
              fill=(71, 85, 105), font=body_font)
    
    draw.text((45, 320), "SNB (Mandible relative to cranial base):", fill=(15, 23, 42), font=bold_font)
    draw.text((350, 320), f"{meas_by_code.get('SNB', 80.0):.1f}° (Norm: 80.0°)", 
              fill=(71, 85, 105), font=body_font)
    
    draw.text((45, 340), "ANB (Maxillo-mandibular relationship):", fill=(15, 23, 42), font=bold_font)
    draw.text((350, 340), f"{anb:.1f}° (Norm: 2.0°)", fill=(71, 85, 105), font=body_font)
    
    # Recommendations
    draw.text((30, 390), "INDICATIVE CLINICAL RECOMMENDATIONS", fill=(15, 23, 42), font=section_font)
    draw.line([(30, 410), (620, 410)], fill=(15, 23, 42), width=2)
    
    recs = []
    if "Class II" in skeletal_class:
        recs.append("- Functional appliance or Class II mechanics when clinically indicated.")
        recs.append("- Dual arch orthodontic alignment with Class II elastics or dental camouflage.")
    elif "Class III" in skeletal_class:
        recs.append("- Orthopedic correction with facemask protraction when clinically indicated.")
        recs.append("- Surgical-orthodontic consultation (LeFort I/BSSO) if patient is skeletally mature.")
    else:
        recs.append("- Leveling, aligning, and finishing with standard non-extraction mechanics.")
    
    if "Hyperdivergent" in vertical_pattern:
        recs.append("- High vertical anchorage control, avoid molar extrusion, consider TADs for intrusion.")
    elif "Hypodivergent" in vertical_pattern:
        recs.append("- Deep bite correction via incisor intrusion or molar extrusion to open bite.")
    
    recs.append("- Retain with custom vacuum-formed retainers and monitor periodontal stability.")
    
    y = 425
    for r in recs:
        draw.text((45, y), r, fill=(15, 23, 42), font=bold_font)
        y += 25
    
    # Signature
    draw.line([(30, 720), (620, 720)], fill=(203, 213, 225), width=1)
    draw.text((30, 735), "AI Validation Signature:", fill=(100, 116, 139), font=body_font)
    draw.rectangle([180, 730, 350, 765], fill=(241, 245, 249))
    draw.text((195, 742), "CEPH-AI CERTIFIED", fill=(2, 132, 199), font=bold_font)
    draw.text((420, 735), "Reviewing Clinician:", fill=(100, 116, 139), font=body_font)
    draw.line([(420, 765), (620, 765)], fill=(15, 23, 42), width=1)
    
    return img
