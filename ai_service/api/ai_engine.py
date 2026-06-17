from __future__ import annotations

import json
import os
from typing import Any, Dict, Generator, Iterable, Optional


def _pretty_lines(title: str, diagnostic_report: Dict[str, Any], treatment_plan: Optional[Dict[str, Any]] = None) -> str:
    lines = [
        f"{title}",
        f"Protocol: {diagnostic_report.get('protocol', 'unknown')} ({diagnostic_report.get('diagnostic_code', 'n/a')})",
        f"Skeletal pattern: {diagnostic_report.get('skeletal_class', 'n/a')}",
        f"Vertical pattern: {diagnostic_report.get('vertical_pattern', 'n/a')}",
        f"Severity: {diagnostic_report.get('severity', 'n/a')}",
    ]
    
    if "craniofacial_patterns" in diagnostic_report:
        lines.append(f"Craniofacial patterns: {', '.join(diagnostic_report['craniofacial_patterns'])}")
        
    if "icd10_codes" in diagnostic_report:
        codes = [f"{c['code']} ({c['description']})" for c in diagnostic_report["icd10_codes"]]
        lines.append(f"Suggested ICD-10 Codes: {', '.join(codes)}")

    if diagnostic_report.get("findings"):
        lines.append("Key findings:")
        for finding in diagnostic_report["findings"]:
            outlier_warn = " [OUTLIER DETECTED]" if finding.get("is_outlier") else ""
            lines.append(f"- {finding.get('measurement')}: {finding.get('label')} ({finding.get('interpretation')}){outlier_warn}")
            
    if treatment_plan:
        primary = treatment_plan.get("primary_recommendation", {})
        lines.append(f"Primary treatment: {primary.get('title', 'n/a')}")
        lines.append(f"Rationale: {primary.get('rationale', 'n/a')}")
        
        if "risk_assessment" in treatment_plan:
            risk = treatment_plan["risk_assessment"]
            lines.append(f"Overall Risk Level: {risk.get('overall_risk_level', 'n/a')}")
            if risk.get("specific_risks"):
                lines.append("Specific Risks:")
                for r in risk["specific_risks"]:
                    lines.append(f"- {r['complication']} (Probability: {r['probability']})")
                    
        if "success_prediction" in treatment_plan:
            success = treatment_plan["success_prediction"]
            lines.append(f"Estimated Success Rate: {success.get('estimated_success_rate', 'n/a')}")

    return "\n".join(lines)


def _fallback_patient_letter(diagnostic_report: Dict[str, Any], treatment_plan: Optional[Dict[str, Any]] = None) -> str:
    primary = (treatment_plan or {}).get("primary_recommendation", {})
    skeletal_class = diagnostic_report.get("skeletal_class", "a balanced")
    vertical_pattern = diagnostic_report.get("vertical_pattern", "balanced")
    severity = diagnostic_report.get("severity", "mild")
    treatment_title = primary.get("title", "observation")
    return (
        f"Your cephalometric analysis suggests {skeletal_class} pattern with a {vertical_pattern} vertical pattern. "
        f"The current severity is {severity}. "
        f"The main treatment direction is {treatment_title}."
    )


def _try_gemini(prompt: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai  # type: ignore
    except Exception:
        return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)
        return text or None
    except Exception:
        return None


def _try_openai(prompt: str) -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a conservative orthodontic reporting assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content if response.choices else None
    except Exception:
        return None


def _provider_chain(provider: str) -> Iterable[str]:
    provider = (provider or "auto").lower()
    if provider == "gemini":
        return ("gemini", "openai")
    if provider == "openai":
        return ("openai", "gemini")
    return ("gemini", "openai")


def _run_provider(prompt: str, provider: str = "auto") -> Dict[str, str]:
    for candidate in _provider_chain(provider):
        if candidate == "gemini":
            text = _try_gemini(prompt)
            if text:
                return {"provider": "gemini", "content": text}
        else:
            text = _try_openai(prompt)
            if text:
                return {"provider": "openai", "content": text}
    return {"provider": "fallback", "content": prompt}


def stream_text(text: str, chunk_size: int = 240) -> Generator[str, None, None]:
    if chunk_size <= 0:
        chunk_size = 240
    for start in range(0, len(text), chunk_size):
        yield text[start : start + chunk_size]


def generate_narrative_diagnosis(
    diagnostic_report: Dict[str, Any],
    treatment_plan: Optional[Dict[str, Any]] = None,
    provider: str = "auto",
) -> Dict[str, str]:
    prompt = _pretty_lines("Clinical narrative diagnosis", diagnostic_report, treatment_plan)
    result = _run_provider(prompt, provider=provider)
    if result["provider"] == "fallback":
        result["content"] = prompt
    return result


def generate_treatment_options(
    diagnostic_report: Dict[str, Any],
    treatment_plan: Dict[str, Any],
    provider: str = "auto",
) -> Dict[str, str]:
    prompt = _pretty_lines("Evidence-based treatment options", diagnostic_report, treatment_plan)
    result = _run_provider(prompt, provider=provider)
    if result["provider"] == "fallback":
        result["content"] = json.dumps(treatment_plan, indent=2)
    return result


def generate_patient_explanation(
    diagnostic_report: Dict[str, Any],
    treatment_plan: Optional[Dict[str, Any]] = None,
    provider: str = "auto",
) -> Dict[str, str]:
    prompt = (
        "Write a short, plain-language explanation for a patient based on this cephalometric report. "
        f"{_pretty_lines('Patient explanation', diagnostic_report, treatment_plan)}"
    )
    result = _run_provider(prompt, provider=provider)
    if result["provider"] == "fallback":
        result["content"] = _fallback_patient_letter(diagnostic_report, treatment_plan)
    return result
