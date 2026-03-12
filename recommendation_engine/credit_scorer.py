import json
import re
import google.generativeai as genai
import os
try:
    import streamlit as st
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    GEMINI_MODEL = st.secrets.get("GEMINI_MODEL", "gemini-2.5-flash")
    FIVE_CS_WEIGHTS = {
        "character": 0.25,
        "capacity": 0.30,
        "capital": 0.20,
        "collateral": 0.15,
        "conditions": 0.10,
    }
except:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = "gemini-2.5-flash"
    FIVE_CS_WEIGHTS = {
        "character": 0.25,
        "capacity": 0.30,
        "capital": 0.20,
        "collateral": 0.15,
        "conditions": 0.10,
    }
from recommendation_engine.ml_model import predict_default

genai.configure(api_key=GEMINI_API_KEY)


def compute_five_cs(financial_data: dict, gst_analysis: dict, research_analysis: dict) -> dict:
    risk_map = {"low": 90, "medium": 60, "high": 30}

    ml_result = predict_default(financial_data)
    ml_score = ml_result["ml_score"]

    overall_risk = "medium"
    if isinstance(research_analysis, dict):
        overall_risk = research_analysis.get("overall_external_risk_rating",
                       research_analysis.get("overall_risk", "medium"))
        if isinstance(overall_risk, str):
            overall_risk = overall_risk.lower().strip()

    character = risk_map.get(overall_risk, 60)

    capacity = min(100, max(0,
        50
        + (10 if financial_data.get("debt_service_coverage", 1) > 1.5 else -10)
        + (10 if financial_data.get("current_ratio", 1) > 1.2 else -10)
        + (10 if financial_data.get("revenue_growth", 0) > 0.1 else -5)
    ))

    capital = min(100, max(0,
        50
        + (20 if financial_data.get("debt_to_equity", 2) < 1.5 else -20)
        + (10 if financial_data.get("net_worth", 0) > 0 else -20)
    ))

    collateral = min(100, max(0,
        50
        + (20 if financial_data.get("collateral_coverage", 0) > 1.2 else -10)
        + (10 if financial_data.get("collateral_type") == "immovable" else 0)
    ))

    conditions = min(100, max(0,
        50
        + (20 if financial_data.get("sector_outlook") == "positive" else -20)
        + (10 if gst_analysis.get("risk_level") == "low" else -10)
    ))

    scores = {
        "character": character,
        "capacity": capacity,
        "capital": capital,
        "collateral": collateral,
        "conditions": conditions
    }

    rule_based_score = sum(scores[c] * FIVE_CS_WEIGHTS[c] for c in scores)
    final_score = round((rule_based_score * 0.5) + (ml_score * 0.5), 2)

    return {
        "five_cs": scores,
        "weighted_score": final_score,
        "ml_score": ml_score,
        "ml_result": ml_result
    }


def make_decision(weighted_score: float, financial_data: dict, ml_score: float = None) -> dict:

    # HARD OVERRIDE RULES
    gst_risk = financial_data.get("gst_risk", "low")

    # Rule 1: High GST risk caps score at CONDITIONAL
    if gst_risk == "high":
        weighted_score = min(weighted_score, 64)

    # Rule 2: High D/E caps score
    if financial_data.get("debt_to_equity", 0) > 3:
        weighted_score = min(weighted_score, 64)

    if weighted_score >= 65:
        decision = "APPROVE"
        requested = financial_data.get("loan_amount_requested", 1000000)
        limit = requested * min(1.0, weighted_score / 100)
        risk_premium = round(8.5 + (100 - weighted_score) * 0.1, 2)
    elif weighted_score >= 45:
        decision = "CONDITIONAL APPROVE"
        requested = financial_data.get("loan_amount_requested", 1000000)
        limit = requested * 0.6
        risk_premium = round(10 + (100 - weighted_score) * 0.15, 2)
    else:
        decision = "REJECT"
        limit = 0
        risk_premium = None

    return {
        "decision": decision,
        "credit_limit": round(limit, 2) if decision != "REJECT" else 0,
        "risk_premium": risk_premium,
        "score": weighted_score,
        "ml_score": round(ml_score, 2) if ml_score else "N/A"
    }


def explain_decision(decision: dict, five_cs: dict, financial_data: dict, research_analysis: dict, ml_result: dict) -> str:
    # Build safe summary of research
    if isinstance(research_analysis, dict):
        risk_rating = research_analysis.get("overall_external_risk_rating",
                      research_analysis.get("overall_risk", "Medium"))
        early_warnings = research_analysis.get("early_warning_signals_if_any", [])
        warnings_text = ", ".join(early_warnings[:2]) if early_warnings else "None detected"
    else:
        risk_rating = "Medium"
        warnings_text = "None detected"

    prompt = f"""You are a senior Indian credit analyst writing a Credit Appraisal Memo.

Write a professional 4-5 sentence explanation for this credit decision.
Be specific — cite actual numbers. Do NOT be generic.

Decision: {decision['decision']}
Credit Score: {decision['score']}/100
Credit Limit: ₹{decision['credit_limit']:,.0f}
Risk Premium: {decision['risk_premium']}%
ML Score: {decision.get('ml_score', 'N/A')}/100
ML Default Probability: {ml_result.get('default_probability', 'N/A')}%

Five Cs: Character={five_cs.get('character')}, Capacity={five_cs.get('capacity')}, Capital={five_cs.get('capital')}, Collateral={five_cs.get('collateral')}, Conditions={five_cs.get('conditions')}

Key Metrics: DSCR={financial_data.get('debt_service_coverage')}, Current Ratio={financial_data.get('current_ratio')}, D/E={financial_data.get('debt_to_equity')}, Collateral Coverage={financial_data.get('collateral_coverage')}x {financial_data.get('collateral_type')}

External Risk Rating: {risk_rating}
Early Warnings: {warnings_text}

Write the explanation now. Professional tone. Indian banking context."""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return (f"Credit decision: {decision['decision']} with score {decision['score']}/100. "
                f"ML model projects {ml_result.get('default_probability', 'N/A')}% default probability. "
                f"Five Cs — Character: {five_cs.get('character')}, Capacity: {five_cs.get('capacity')}, "
                f"Capital: {five_cs.get('capital')}, Collateral: {five_cs.get('collateral')}, "
                f"Conditions: {five_cs.get('conditions')}. Manual review recommended.")


def natural_language_explainer(decision: dict, five_cs: dict, gst_analysis: dict, ml_result: dict, financial_data: dict) -> str:
    
    # Build the single most important reason
    top_reason = ""
    if gst_analysis.get("discrepancy_pct", 0) > 40:
        top_reason = f"a {gst_analysis.get('discrepancy_pct')}% GST-bank discrepancy suggesting revenue inflation"
    elif five_cs.get("character", 100) < 40:
        top_reason = "high external risk detected — regulatory non-compliance and MCA violations"
    elif ml_result.get("default_probability", 0) > 50:
        top_reason = f"ML model projects {ml_result.get('default_probability')}% default probability"
    elif five_cs.get("capacity", 0) >= 70:
        top_reason = f"strong repayment capacity with DSCR of {financial_data.get('debt_service_coverage')}x"
    else:
        top_reason = f"overall credit score of {decision.get('score')}/100"

    prompt = f"""You are a senior Indian credit analyst. Write ONE crisp paragraph (3-4 sentences max) explaining this decision IN PLAIN ENGLISH. 

Start with exactly: "I {decision['decision'].lower()} this loan because {top_reason}."

Then mention:
- The single biggest risk factor from SHAP: {list(ml_result.get('risk_factors', {}).keys())[:1]}
- The single biggest positive: {list(ml_result.get('positive_factors', {}).keys())[:1]}
- Final credit limit: ₹{decision.get('credit_limit', 0):,.0f} at {decision.get('risk_premium')}% risk premium

Use simple language. No jargon. As if explaining to a business owner why their loan was approved or rejected."""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text
    except:
        return f"I {decision['decision'].lower()} this loan because {top_reason}. Final credit limit: ₹{decision.get('credit_limit', 0):,.0f} at {decision.get('risk_premium')}% risk premium."