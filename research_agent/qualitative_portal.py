import json
import re
import google.generativeai as genai
import os
try:
    import streamlit as st
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    GEMINI_MODEL = st.secrets.get("GEMINI_MODEL", "gemini-2.5-flash")
except:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = "gemini-2.5-flash"

genai.configure(api_key=GEMINI_API_KEY)


def process_qualitative_notes(notes: list[str], current_score: float) -> dict:
    notes_text = "\n".join([f"- {note}" for note in notes])

    prompt = f"""
    You are a senior Indian credit analyst. A credit officer has submitted the following
    qualitative observations after visiting the borrower's premises and conducting
    management interviews:

    {notes_text}

    Current quantitative credit score: {current_score}/100

    Based on these observations:
    1. Identify positive and negative signals
    2. Suggest a score adjustment (-20 to +20) with reasoning
    3. Flag any observations that are deal-breakers
    4. Provide an updated risk assessment

    Respond in structured JSON format only.
    """

    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    clean = re.sub(r"```json|```", "", response.text).strip()

    try:
        parsed = json.loads(clean)
        adjustment = parsed.get("score_adjustment", 0)
        adjusted_score = max(0, min(100, current_score + adjustment))
        parsed["adjusted_score"] = adjusted_score
        return parsed
    except:
        return {
            "raw_response": response.text,
            "adjusted_score": current_score
        }