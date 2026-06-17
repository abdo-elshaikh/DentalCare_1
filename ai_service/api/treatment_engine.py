from __future__ import annotations

from typing import Any, Dict, List, Optional


def _plan_item(
    title: str,
    rationale: str,
    evidence_level: str,
    timeline_months: str,
    referrals: List[str],
    contraindications: List[str],
    alternative: str,
    evidence_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "title": title,
        "rationale": rationale,
        "evidence_level": evidence_level,
        "timeline_months": timeline_months,
        "referrals": referrals,
        "contraindications": contraindications,
        "alternative": alternative,
        "evidence_refs": evidence_refs or [],
    }


def _assess_complication_risk(
    diagnostic_report: Dict[str, Any],
    age: Optional[int] = None,
) -> Dict[str, Any]:
    risks = []
    overall_risk_level = "Low"
    
    vertical_pattern = diagnostic_report.get("vertical_pattern", "Normodivergent")
    severity = diagnostic_report.get("severity", "mild")
    dental_pattern = diagnostic_report.get("dental_pattern", "balanced incisor inclination")
    skeletal_class = diagnostic_report.get("skeletal_class", "Class I")
    
    adult = age is not None and age >= 18
    
    if vertical_pattern == "Hyperdivergent":
        risks.append({"complication": "Anterior Open Bite Relapse", "probability": "Moderate", "mitigation": "Strict vertical control, possible posterior intrusion (TADs)."})
        overall_risk_level = "Moderate"
        
    if "proclined lower incisors" in dental_pattern:
        risks.append({"complication": "Gingival Recession / Fenestration", "probability": "High", "mitigation": "Periodontal monitoring, torque control, consider extraction/IPR to retract incisors."})
        overall_risk_level = "High" if adult else "Moderate"
        
    if severity == "severe":
        risks.append({"complication": "Root Resorption", "probability": "Moderate", "mitigation": "Minimize treatment duration, use light continuous forces, take progress radiographs."})
        overall_risk_level = "High"
        
    if adult and ("Class II" in skeletal_class or "Class III" in skeletal_class) and severity in ["moderate", "severe"]:
        risks.append({"complication": "Soft Tissue Profile Worsening (if camouflaged)", "probability": "High", "mitigation": "Orthognathic surgical consultation prior to commencing camouflage."})
        overall_risk_level = "High"
        
    if not risks:
        risks.append({"complication": "Standard Orthodontic Risks (Decalcification, mild root blunting)", "probability": "Low", "mitigation": "Good oral hygiene, routine monitoring."})
        
    return {
        "overall_risk_level": overall_risk_level,
        "specific_risks": risks
    }


def _predict_treatment_success(
    skeletal_class: str,
    severity: str,
    age: Optional[int],
    primary_title: str
) -> Dict[str, Any]:
    success_rate = "High (>90%)"
    factors = []
    
    adult = age is not None and age >= 18
    
    if severity == "mild":
        success_rate = "Very High (>95%)"
        factors.append("Mild discrepancy is highly responsive to standard mechanics.")
    elif severity == "severe":
        if adult:
            if "Orthognathic" in primary_title or "LeFort" in primary_title:
                success_rate = "High (85-90%) with Surgery"
                factors.append("Surgical correction provides predictable skeletal resolution.")
            else:
                success_rate = "Moderate (60-75%) for Camouflage"
                factors.append("Severe adult discrepancies are difficult to camouflage without compromising periodontal health or profile.")
        else:
            success_rate = "Moderate to High (75-85%)"
            factors.append("Growing patients have favorable adaptation, but severe patterns require excellent compliance.")
            
    if "facemask" in primary_title.lower() or "herbst" in primary_title.lower():
        factors.append("Success is heavily dependent on patient compliance with the appliance.")
        
    return {
        "estimated_success_rate": success_rate,
        "predictive_factors": factors
    }


def build_treatment_plan(
    diagnostic_report: Dict[str, Any],
    age: Optional[int] = None,
    sex: Optional[str] = None,
) -> Dict[str, Any]:
    skeletal_class = diagnostic_report.get("skeletal_class", "Class I")
    vertical_pattern = diagnostic_report.get("vertical_pattern", "Normodivergent")
    severity = diagnostic_report.get("severity", "mild")
    dental_pattern = diagnostic_report.get("dental_pattern", "balanced incisor inclination")
    diagnostic_code = diagnostic_report.get("diagnostic_code", "CI-NVD-L")

    growing = age is not None and age < 18
    young = age is not None and age < 16
    adult = age is not None and age >= 18

    primary = _plan_item(
        title="Observation and interceptive monitoring",
        rationale="The present findings do not justify immediate orthopaedic intervention.",
        evidence_level="III",
        timeline_months="6-12",
        referrals=["orthodontics"],
        contraindications=["rapidly progressive skeletal discrepancy"],
        alternative="Targeted alignment and finishing mechanics",
        evidence_refs=["Clinical consensus: interceptive monitoring (2017 guideline)"] ,
    )

    secondary: List[Dict[str, Any]] = []

    if skeletal_class == "Class II" and growing:
        primary = _plan_item(
            title="Herbst or Twin Block with vertical control",
            rationale="Growing Class II patients with vertical excess benefit from mandibular advancement and intrusion control.",
            evidence_level="II",
            timeline_months="12-18",
            referrals=["orthodontics", "growth monitoring"],
            contraindications=["advanced skeletal maturity", "noncompliance"],
            alternative="Camouflage mechanics with bite correction",
            evidence_refs=["Pancherz 1997; Herbst appliance outcomes", "Cozza 2004; Twin-block effectiveness"],
        )
        secondary.append(
            _plan_item(
                title="Temporary anchorage device assisted intrusion",
                rationale="Useful when hyperdivergence and dentoalveolar compensation are both present.",
                evidence_level="II",
                timeline_months="6-12",
                referrals=["orthodontics"],
                contraindications=["poor periodontal support"],
                alternative="Conventional vertical elastics",
                    evidence_refs=["JCO 2015; TADs for intrusion", "Systematic review 2018; TADs outcomes"],
            )
        )
    elif skeletal_class == "Class II" and adult:
        primary = _plan_item(
            title="Orthognathic evaluation with camouflage as backup",
            rationale="Adult Class II patterns frequently require skeletal correction if the discrepancy is moderate or severe.",
            evidence_level="I",
            timeline_months="18-30",
            referrals=["orthognathic surgery", "orthodontics"],
            contraindications=["untreated periodontal disease"],
            alternative="Orthodontic camouflage with incisor compensation",
            evidence_refs=["Proffit et al. 2013; Orthognathic outcomes review"],
        )
        secondary.append(
            _plan_item(
                title="Camouflage orthodontics",
                rationale="Can be used when facial goals are limited and the skeletal discrepancy is mild.",
                evidence_level="III",
                timeline_months="18-24",
                referrals=["orthodontics"],
                contraindications=["severe profile discrepancy"],
                alternative="Combined surgical-orthodontic correction",
                evidence_refs=["Clinical review: camouflage strategies (2016)"] ,
            )
        )
    elif skeletal_class == "Class III" and young:
        primary = _plan_item(
            title="Facemask protraction with maxillary expansion",
            rationale="Early growth modification is the most evidence-supported option for developing Class III cases.",
            evidence_level="II",
            timeline_months="9-18",
            referrals=["orthodontics", "growth monitoring"],
            contraindications=["advanced skeletal maturity"],
            alternative="Observation until growth spurt clarifies the pattern",
            evidence_refs=["Baccetti 2009; facemask RCTs", "Systematic review 2014; protraction facemask"],
        )
        secondary.append(
            _plan_item(
                title="RME or MARPE adjunctive protocol",
                rationale="Expansion can improve transverse deficiency and support protraction mechanics.",
                evidence_level="II",
                timeline_months="4-8",
                referrals=["orthodontics"],
                contraindications=["severe periodontal limitation"],
                alternative="Slow expansion with occlusal monitoring",
                evidence_refs=["Wertz 2012; RME effects", "MARPE consensus 2019"],
            )
        )
    elif skeletal_class == "Class III" and adult:
        primary = _plan_item(
            title="Combined LeFort I and BSSO evaluation",
            rationale="Adult Class III discrepancies with facial imbalance are usually best addressed surgically.",
            evidence_level="I",
            timeline_months="18-30",
            referrals=["orthognathic surgery", "orthodontics"],
            contraindications=["medical unfitness for surgery"],
            alternative="Camouflage with dental compensation if discrepancy is mild",
            evidence_refs=["Orthognathic surgery outcomes (Proffit 2013)"] ,
        )
        secondary.append(
            _plan_item(
                title="Orthodontic camouflage",
                rationale="Acceptable when the patient declines surgery and the facial discrepancy is limited.",
                evidence_level="III",
                timeline_months="18-24",
                referrals=["orthodontics"],
                contraindications=["severe sagittal disharmony"],
                alternative="Combined surgical correction",
                evidence_refs=["Camouflage outcomes review 2017"],
            )
        )
    elif "proclined lower incisors" in dental_pattern:
        primary = _plan_item(
            title="Extraction protocol with controlled retraction",
            rationale="Lower incisor proclination often improves with space creation and torque-controlled retraction.",
            evidence_level="II",
            timeline_months="12-24",
            referrals=["orthodontics"],
            contraindications=["severe anchorage loss risk"],
            alternative="Non-extraction alignment with torque control",
            evidence_refs=["Extraction vs non-extraction outcomes (JCO 2014)"] ,
        )
        secondary.append(
            _plan_item(
                title="Anchorage reinforcement",
                rationale="TADs or reinforced anchorage reduce adverse tipping during retraction.",
                evidence_level="II",
                timeline_months="6-18",
                referrals=["orthodontics"],
                contraindications=["patient declines auxiliary anchorage"],
                alternative="Conventional anchorage control",
                evidence_refs=["TADs anchorage review 2016"],
            )
        )
    elif skeletal_class == "Class I" and severity == "mild":
        primary = _plan_item(
            title="Non-extraction alignment and finishing",
            rationale="Balanced sagittal relationships with mild findings usually respond to alignment-focused therapy.",
            evidence_level="III",
            timeline_months="10-18",
            referrals=["orthodontics"],
            contraindications=["crowding beyond space availability"],
            alternative="Selective extraction if crowding worsens",
            evidence_refs=["Contemporary orthodontics review 2018"] ,
        )

    if vertical_pattern == "Hyperdivergent":
        secondary.append(
            _plan_item(
                title="Vertical control adjuncts",
                rationale="Control of posterior eruption and molar position is important in hyperdivergent cases.",
                evidence_level="II",
                timeline_months="6-18",
                referrals=["orthodontics"],
                contraindications=["poor compliance with elastics"],
                alternative="Observation with growth and posture review",
                evidence_refs=["JCO 2015; vertical control review"],
            )
        )

    # Calculate Risk and Success profiles
    risk_assessment = _assess_complication_risk(diagnostic_report, age)
    success_prediction = _predict_treatment_success(skeletal_class, severity, age, primary["title"])

    # Build concise next steps tailored to the diagnostic context
    next_steps: List[str] = []
    next_steps.append("Confirm clinical records: intraoral photos, study models or digital scans, panoramic radiograph.")
    next_steps.append("Perform periodontal assessment and complete dental health review before orthodontic planning.")
    if age is not None and age < 18:
        next_steps.append("Establish growth monitoring schedule and document skeletal maturity (CVS/hand-wrist if available).")
    next_steps.append("Discuss treatment goals with the patient/guardian and obtain informed consent for chosen pathway.")

    return {
        "diagnostic_code": diagnostic_code,
        "skeletal_class": skeletal_class,
        "vertical_pattern": vertical_pattern,
        "severity": severity,
        "age": age,
        "sex": sex,
        "primary_recommendation": primary,
        "alternative_recommendations": secondary,
        "treatment_objectives": [
            "Stabilize the skeletal relationship",
            "Control vertical dimension",
            "Normalize incisor inclination when indicated",
        ],
        "risk_assessment": risk_assessment,
        "success_prediction": success_prediction,
        "next_steps": next_steps,
        "evidence_summary": {
            "primary_evidence_level": primary.get("evidence_level"),
            "references": list({ref for item in ([primary] + secondary) for ref in item.get("evidence_refs", [])}),
        },
    }
