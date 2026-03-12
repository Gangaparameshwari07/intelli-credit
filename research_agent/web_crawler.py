import time
import json
import re
from tavily import TavilyClient
import google.generativeai as genai
import os
try:
    import streamlit as st
    TAVILY_API_KEY = st.secrets.get("TAVILY_API_KEY", os.environ.get("TAVILY_API_KEY", ""))
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    GEMINI_MODEL = st.secrets.get("GEMINI_MODEL", "gemini-2.5-flash")
except:
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = "gemini-2.5-flash"

tavily = TavilyClient(api_key=TAVILY_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

FALLBACK_ANALYSIS = json.dumps({
    "promoter_reputation_and_background": "Web research unavailable — manual verification recommended.",
    "litigation_fraud_or_regulatory_actions": "Unable to retrieve data. Please check MCA portal manually.",
    "sector_headwinds_or_tailwinds": "Sector data unavailable. Analyst should review RBI sectoral reports.",
    "recent_news_that_impacts_creditworthiness": "No recent news retrieved.",
    "early_warning_signals_if_any": "System could not retrieve early warning data.",
    "overall_external_risk_rating": "Medium",
    "risk_justification": "Defaulted to medium risk due to API unavailability."
})


def research_company(company_name: str) -> dict:
    # Extract sector from company name context
    sector = "textile" if any(w in company_name.lower() for w in ["textile", "fabric", "garment"]) else "MSME"
    
    queries = [
        f"{company_name} latest news India",
        f"{company_name} promoter fraud litigation India",
        f"{company_name} MCA regulatory action",
        f"{company_name} sector outlook credit",
        f"latest RBI circulars for {sector} 2025",
        f"Government of India PLI scheme updates for {sector} MSMEs",
    ]

    all_results = []
    for query in queries:
        try:
            results = tavily.search(query=query, max_results=2)
            all_results.extend(results.get("results", []))
            time.sleep(1.5)
        except Exception as e:
            print(f"Tavily search failed for query '{query}': {e}")
            time.sleep(2)
            continue

    if not all_results:
        return {
            "company": company_name,
            "sources": [],
            "analysis": FALLBACK_ANALYSIS
        }

    return synthesize_research(company_name, all_results)


def synthesize_research(company_name: str, raw_results: list) -> dict:
    content = "\n\n".join([
        f"Source {i+1}: {r['url']}\n{r['content'][:500]}"
        for i, r in enumerate(raw_results)
    ])

    prompt = f"""You are a senior Indian credit analyst doing due diligence on {company_name}.
Based on the web research below, provide a structured credit analysis.

Return ONLY a valid JSON object with exactly these keys:
{{
    "promoter_reputation_and_background": "...",
    "litigation_fraud_or_regulatory_actions": {{
        "regulatory_actions": [],
        "litigation": [],
        "fraud": []
    }},
    "sector_headwinds_or_tailwinds": {{
        "headwinds": [],
        "tailwinds": []
    }},
    "recent_news_that_impacts_creditworthiness": {{
        "positive_impact": [],
        "negative_impact": []
    }},
    "early_warning_signals_if_any": [],
    "overall_external_risk_rating": "Low/Medium/High",
    "risk_justification": "..."
}}

Research Data:
{content[:6000]}

Return ONLY the JSON object. No extra text."""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        clean = re.sub(r"```json|```", "", response.text).strip()
        json.loads(clean)
        analysis_text = clean
    except Exception as e:
        print(f"Gemini synthesis failed: {e}")
        analysis_text = FALLBACK_ANALYSIS

    return {
        "company": company_name,
        "sources": [r["url"] for r in raw_results],
        "analysis": analysis_text
    }