"""
Intelli-Credit — Advanced PDF Parser
Handles ALL types of unstructured financial documents:
- Scanned PDFs (image-based)
- Digital PDFs with complex tables
- Multi-page financial statements
- Merged cells, multi-level headers
- Hand-typed / non-standard formatting

Strategy:
1. Try pdfplumber text + table extraction (fast, free)
2. Convert pages to images → Gemini Vision (handles scans)
3. Page-level table extraction → structured JSON
4. Final aggregation via Gemini → clean financial_data
"""

import pdfplumber
import base64
import json
import re
import os
import io
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL

genai.configure(api_key=GEMINI_API_KEY)

DOC_TYPE_PROMPTS = {
    "annual_report": """Extract ALL financial data from this Indian Annual Report page.
Focus on: Revenue/Turnover, EBITDA, Net Profit/PAT, Finance Costs, Depreciation,
Total Assets, Fixed Assets, Current Assets, Total Liabilities, Net Worth, Equity, Total Debt,
Operating CF, Investing CF, Financing CF,
DSCR, Current Ratio, D/E Ratio, ROE, ROA, Interest Coverage, Revenue Growth %""",

    "alm": """Extract ALL ALM data. Focus on:
Maturity buckets (1day, 2-7days, 8-14days, 15-30days, 31-90days, 91-180days, 181days-1yr, 1-3yr, 3-5yr, >5yr)
For each bucket: Assets, Liabilities, Gap, Cumulative Gap
LCR (Liquidity Coverage Ratio), NSFR (Net Stable Funding Ratio)
Total Assets, Total Liabilities, all Liquidity Gaps""",

    "shareholding_pattern": """Extract ALL shareholding data. Focus on:
Promoter holding % (Indian + Foreign), FII %, DII %, Mutual Fund %,
Public/Retail holding %, Total shares, Paid-up capital, Pledged shares %,
Top shareholders with % stakes""",

    "borrowing_profile": """Extract ALL borrowing data. Focus on:
Lender names and outstanding amounts, Secured vs Unsecured split,
Interest rates per facility, Repayment schedule/EMI,
Sanction vs Utilized, Debt maturity profile, Average cost of borrowing""",

    "portfolio_data": """Extract ALL portfolio data. Focus on:
Total Portfolio/AUM, Gross NPA %, Net NPA %,
Stage 1%, Stage 2%, Stage 3% (ECL), PAR 30, PAR 60, PAR 90,
Collection efficiency %, Disbursements, Sector-wise split, Write-offs""",

    "default": """Extract ALL financial data, numbers, ratios, percentages visible on this page.
Include all tables and figures even if formatting is unusual or document is scanned."""
}

FINAL_AGGREGATION_PROMPT = """Senior Indian credit analyst. Aggregate extracted data into clean JSON.

Raw data: {raw_data}
Document type: {doc_type}

Return JSON with ONLY fields actually found:
{{
  "revenue": number, "net_profit": number, "ebitda": number,
  "total_assets": number, "total_liabilities": number, "net_worth": number,
  "total_debt": number, "debt_service_coverage": number, "current_ratio": number,
  "debt_to_equity": number, "interest_coverage": number, "revenue_growth": number,
  "operating_cash_flow": number, "promoter_holding_pct": number,
  "npa_pct": number, "stage_3_pct": number, "par_90": number,
  "total_portfolio_size": number, "liquidity_gap_30d": number,
  "average_interest_rate": number, "year": string
}}
Rules: monetary values in original units, ratios as decimals (1.4 not 140),
growth as decimal (0.15 for 15%), most recent year if multiple, omit missing fields.
Return ONLY valid JSON."""


def is_scanned_pdf(pdf_path: str) -> bool:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            text = "".join(page.extract_text() or "" for page in pdf.pages[:3])
            return len(text) < total_pages * 80
    except:
        return True


def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        full_text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
                for table in (page.extract_tables() or []):
                    for row in table:
                        if row:
                            full_text += " | ".join(str(c or "").strip() for c in row) + "\n"
        return full_text.strip()
    except:
        return ""


def pdf_pages_to_base64(pdf_path: str, max_pages: int = 8) -> list:
    images = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages]):
                try:
                    img = page.to_image(resolution=150)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    buf.seek(0)
                    b64 = base64.b64encode(buf.read()).decode()
                    images.append({"page": i + 1, "data": b64})
                except:
                    continue
    except:
        pass
    return images


def _parse_json_response(text: str) -> dict:
    clean = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(clean)
    except:
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return {}


def extract_page_with_gemini_vision(image_b64: str, doc_type: str, page_num: int) -> dict:
    focus = DOC_TYPE_PROMPTS.get(doc_type.lower().replace(" ", "_"), DOC_TYPE_PROMPTS["default"])
    prompt = f"Page {page_num} of Indian financial document.\n{focus}\nReturn ONLY valid JSON. Empty {{}} if no financial data."
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content([{"mime_type": "image/png", "data": image_b64}, prompt])
        return _parse_json_response(response.text)
    except:
        return {}


def extract_from_text_with_gemini(text: str, doc_type: str) -> dict:
    focus = DOC_TYPE_PROMPTS.get(doc_type.lower().replace(" ", "_"), DOC_TYPE_PROMPTS["default"])
    prompt = f"Extract financial data. Type: {doc_type}\n{focus}\n\nText:\n{text[:4500]}\n\nReturn ONLY valid JSON."
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        return _parse_json_response(response.text)
    except:
        return {}


def rule_based_extraction(text: str) -> dict:
    """Fast regex extraction — zero API calls."""
    result = {}
    t = text.lower()
    patterns = {
        "revenue":               r"(?:revenue|turnover|net sales|total income)[^\d]{0,20}([\d,]+(?:\.\d+)?)",
        "net_profit":            r"(?:net profit|pat\b|profit after tax)[^\d]{0,20}([\d,]+(?:\.\d+)?)",
        "ebitda":                r"(?:ebitda|operating profit)[^\d]{0,20}([\d,]+(?:\.\d+)?)",
        "total_assets":          r"total assets?[^\d]{0,20}([\d,]+(?:\.\d+)?)",
        "net_worth":             r"(?:net worth|shareholders.{0,5}equity)[^\d]{0,20}([\d,]+(?:\.\d+)?)",
        "total_debt":            r"(?:total debt|total borrowings?)[^\d]{0,20}([\d,]+(?:\.\d+)?)",
        "current_ratio":         r"current ratio[^\d]{0,10}([\d.]+)",
        "debt_to_equity":        r"(?:d/e ratio|debt.{0,5}equity)[^\d]{0,10}([\d.]+)",
        "debt_service_coverage": r"(?:dscr|debt service coverage)[^\d]{0,10}([\d.]+)",
        "interest_coverage":     r"interest coverage[^\d]{0,10}([\d.]+)",
        "promoter_holding_pct":  r"promoter.{0,30}?([\d.]+)\s*%",
        "npa_pct":               r"(?:gross npa|npa %|npa ratio)[^\d]{0,10}([\d.]+)",
        "par_90":                r"par\s*90[^\d]{0,10}([\d.]+)",
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, t)
        if match:
            try:
                result[field] = float(match.group(1).replace(",", ""))
            except:
                pass
    return result


def check_cibil_dpd(text: str) -> dict:
    t = text.lower()
    dpd_matches = re.findall(r'dpd[^\d]{0,5}(\d+)', t)
    red_flags = [k for k in ["wilful default", "npa account", "written off", "suit filed", "strike off"] if k in t]
    return {
        "has_dpd_mentions": bool(dpd_matches) or any(k in t for k in ["days past due", "overdue"]),
        "dpd_values": [int(m) for m in dpd_matches[:5]],
        "cibil_risk": any(int(m) > 30 for m in dpd_matches) if dpd_matches else False,
        "red_flags": red_flags
    }


def _aggregate(raw_data: dict, doc_type: str) -> dict:
    """Final Gemini aggregation — cleans and standardizes."""
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = FINAL_AGGREGATION_PROMPT.format(
            raw_data=json.dumps(raw_data, indent=2)[:3000],
            doc_type=doc_type
        )
        response = model.generate_content(prompt)
        result = _parse_json_response(response.text)
        return result if result else raw_data
    except:
        return raw_data


def analyze_document(file_path: str, doc_type: str = "annual_report") -> dict:
    """
    Main entry point. Handles any unstructured financial document.
    Auto-detects scanned vs digital. Multi-strategy extraction.
    """
    result = {
        "financials": {}, "cibil_dpd": {},
        "extraction_method": "none", "pages_processed": 0,
        "confidence": "low", "doc_type": doc_type,
    }

    if not os.path.exists(file_path):
        result["error"] = "File not found"
        return result

    ext = file_path.split(".")[-1].lower()

    # ── Images → Gemini Vision directly ──
    if ext in ["jpg", "jpeg", "png"]:
        try:
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            raw = extract_page_with_gemini_vision(b64, doc_type, 1)
            final = _aggregate(raw, doc_type) if raw else {}
            result.update({"financials": final, "extraction_method": "gemini_vision_image",
                           "pages_processed": 1, "confidence": "high" if len(final) >= 3 else "medium"})
        except Exception as e:
            result["error"] = str(e)
        return result

    if ext != "pdf":
        result["error"] = f"Not a PDF — use excel_extractor for {ext} files"
        return result

    # ── PDF ──
    all_data = {}
    scanned = is_scanned_pdf(file_path)

    if scanned:
        # SCANNED → vision on every page
        result["extraction_method"] = "gemini_vision_scanned_pdf"
        images = pdf_pages_to_base64(file_path, max_pages=8)
        result["pages_processed"] = len(images)
        for img in images:
            page_data = extract_page_with_gemini_vision(img["data"], doc_type, img["page"])
            if page_data:
                all_data.update(page_data)
    else:
        # DIGITAL → text + tables + gemini + selective vision on complex pages
        result["extraction_method"] = "text_tables_gemini"
        text = extract_text_from_pdf(file_path)

        try:
            with pdfplumber.open(file_path) as pdf:
                result["pages_processed"] = len(pdf.pages)
                total = len(pdf.pages)
        except:
            total = 1

        # Layer 1: Fast rule-based (free)
        all_data.update(rule_based_extraction(text))

        # Layer 2: CIBIL / DPD check
        result["cibil_dpd"] = check_cibil_dpd(text)

        # Layer 3: Gemini text extraction
        all_data.update(extract_from_text_with_gemini(text, doc_type))

        # Layer 4: Vision on key pages for complex tables (long docs)
        if total >= 5:
            try:
                images = pdf_pages_to_base64(file_path, max_pages=min(total, 10))
                key_idx = set(list(range(3)) + list(range(max(0, total - 2), total)))
                for img in images:
                    if img["page"] - 1 in key_idx:
                        page_data = extract_page_with_gemini_vision(img["data"], doc_type, img["page"])
                        if page_data:
                            all_data.update(page_data)
            except:
                pass

    # ── Final aggregation ──
    if all_data:
        final = _aggregate(all_data, doc_type)
        result["financials"] = final
        result["confidence"] = "high" if len(final) >= 5 else "medium" if len(final) >= 2 else "low"

    return result