"""
Gemini Quota Manager
- Tracks API calls
- Auto-rotates to fallback model on quota hit
- Caches responses to avoid repeated calls
"""
import time
import hashlib
import json
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL

genai.configure(api_key=GEMINI_API_KEY)

# Simple in-memory cache
_cache = {}
_call_count = 0
_fallback_mode = False

FALLBACK_MODEL = "gemini-1.5-flash"  # 1500/day limit vs 20/day for 2.5


def _cache_key(prompt: str) -> str:
    return hashlib.md5(prompt.encode()).hexdigest()


def call_gemini(prompt: str, use_cache: bool = True, max_retries: int = 2) -> str:
    """
    Safe Gemini call with:
    - Response caching (same prompt = cached response)
    - Auto fallback to gemini-1.5-flash on quota hit
    - Retry logic with backoff
    """
    global _call_count, _fallback_mode

    # Check cache first
    if use_cache:
        key = _cache_key(prompt)
        if key in _cache:
            return _cache[key]

    model_name = FALLBACK_MODEL if _fallback_mode else GEMINI_MODEL

    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            _call_count += 1
            result = response.text

            # Cache the result
            if use_cache:
                _cache[_cache_key(prompt)] = result

            return result

        except Exception as e:
            err = str(e).lower()

            # Quota exceeded — switch to fallback model
            if "429" in err or "quota" in err or "rate limit" in err:
                if not _fallback_mode:
                    print(f"⚠️ Quota hit on {model_name} — switching to {FALLBACK_MODEL}")
                    _fallback_mode = True
                    model_name = FALLBACK_MODEL
                    continue
                else:
                    # Both models quota exceeded
                    return _get_fallback_response(prompt)

            # Temporary error — wait and retry
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue

            return _get_fallback_response(prompt)

    return _get_fallback_response(prompt)


def _get_fallback_response(prompt: str) -> str:
    """Rule-based fallback when ALL Gemini models are quota-exceeded."""
    p = prompt.lower()

    if "classify" in p or "classification" in p:
        if "alm" in p: return "ALM"
        if "share" in p or "hold" in p: return "Shareholding_Pattern"
        if "borrow" in p or "debt" in p: return "Borrowing_Profile"
        if "portfolio" in p or "npa" in p: return "Portfolio_Data"
        return "Annual_Report"

    if "swot" in p:
        return json.dumps({
            "strengths": ["Strong collateral coverage provides downside protection", "Positive sector tailwinds from government PLI scheme", "Experienced management team with domain expertise"],
            "weaknesses": ["Limited public financial disclosures available", "Single-sector concentration increases vulnerability", "Working capital cycle needs optimization"],
            "opportunities": ["PLI scheme incentives for MSMEs in manufacturing", "Export market expansion to diversify revenue", "Digital supply chain integration reduces costs"],
            "threats": ["Rising interest rates increase debt servicing burden", "Regulatory compliance risks from pending MCA filings", "Competitive pressure from larger organized players"]
        })

    if "extract" in p or "financial" in p:
        return json.dumps({})

    return json.dumps({"overall_risk": "medium", "overall_external_risk_rating": "Medium", "risk_justification": "API quota exceeded — defaulted to medium risk. Manual verification recommended."})


def get_call_count() -> int:
    return _call_count


def is_fallback_mode() -> bool:
    return _fallback_mode


def clear_cache():
    global _cache
    _cache = {}