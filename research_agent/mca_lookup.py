import time
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


def lookup_mca(company_name: str) -> dict:
    queries = [
        f"{company_name} MCA Ministry Corporate Affairs India",
        f"{company_name} ROC charges director DIN India",
        f"{company_name} court case litigation NCLT India",
    ]

    all_results = []
    for query in queries:
        try:
            results = tavily.search(query=query, max_results=2)
            all_results.extend(results.get("results", []))
            time.sleep(1.5)
        except Exception as e:
            print(f"MCA Tavily failed: {e}")
            time.sleep(2)
            continue

    if not all_results:
        return {
            "status": "unavailable",
            "findings": "MCA lookup unavailable — verify manually at mca.gov.in and ecourts.gov.in",
            "sources": [],
            "risk": "unknown"
        }

    content = "\n\n".join([
        f"Source {i+1}: {r['url']}\n{r['content'][:400]}"
        for i, r in enumerate(all_results)
    ])

    prompt = f"""You are a senior Indian credit analyst. Analyze MCA and legal data for {company_name}.

Provide findings on:
1. Director details and DIN numbers
2. Charges or liens registered
3. ROC compliance status
4. Court cases or litigation
5. Overall legal risk: Low / Medium / High

Research:
{content[:5000]}

Write in clear professional paragraphs. Be specific about findings."""

    try:
        time.sleep(12)  # Rate limiting before Gemini call
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        findings = response.text
    except Exception as e:
        findings = f"MCA analysis failed: {e}. Please verify manually at mca.gov.in"

    return {
        "company": company_name,
        "sources": [r["url"] for r in all_results],
        "findings": findings,
        "status": "completed"
    }