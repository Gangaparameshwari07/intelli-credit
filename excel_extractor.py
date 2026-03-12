"""
Excel Extractor for Intelli-Credit Engine
Handles complex, non-standard financial tables from:
- ALM (Asset Liability Management)
- Shareholding Pattern
- Borrowing Profile
- Annual Reports (P&L, Balance Sheet, Cashflow)
- Portfolio Cuts / Performance Data
"""

import pandas as pd
import numpy as np
import openpyxl
import re
import json
import google.generativeai as genai
import os
try:
    import streamlit as st
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    GEMINI_MODEL = "gemini-2.5-flash"
except:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = "gemini-2.5-flash"

genai.configure(api_key=GEMINI_API_KEY)

# ── Keyword maps for smart column detection ──
FINANCIAL_KEYWORDS = {
    "revenue":          ["revenue", "turnover", "sales", "income from operations", "net sales", "total income"],
    "net_profit":       ["net profit", "pat", "profit after tax", "net income", "profit for the year"],
    "gross_profit":     ["gross profit", "gross margin", "ebitda"],
    "total_assets":     ["total assets", "assets total", "total asset"],
    "total_liabilities":["total liabilities", "liabilities total", "total liability"],
    "net_worth":        ["net worth", "shareholders equity", "shareholders' equity", "equity", "book value"],
    "debt_to_equity":   ["debt to equity", "d/e ratio", "leverage ratio", "d:e"],
    "current_ratio":    ["current ratio", "liquidity ratio"],
    "debt_service_coverage": ["dscr", "debt service coverage", "debt service cover"],
    "revenue_growth":   ["revenue growth", "sales growth", "yoy growth", "growth %"],
    "ebitda":           ["ebitda", "operating profit", "pbit"],
    "cash_flow":        ["cash flow", "net cash", "operating cash"],
    "total_debt":       ["total debt", "total borrowings", "total loans", "total borrowing"],
    "secured_debt":     ["secured loans", "secured debt", "secured borrowings"],
    "unsecured_debt":   ["unsecured loans", "unsecured debt", "unsecured borrowings"],
    "npa_pct":          ["npa", "non performing", "gross npa", "net npa", "npa %", "npa ratio"],
    "stage_1_pct":      ["stage 1", "stage i", "performing assets"],
    "stage_2_pct":      ["stage 2", "stage ii", "special mention", "sma"],
    "stage_3_pct":      ["stage 3", "stage iii", "sub standard", "doubtful", "loss"],
    "par_30":           ["par 30", "par>30", "par > 30", "overdue 30"],
    "par_90":           ["par 90", "par>90", "par > 90", "overdue 90"],
    "promoter_holding_pct": ["promoter", "promoter holding", "promoter %", "promoter shareholding"],
    "institutional_holding_pct": ["institutional", "fii", "dii", "mutual fund", "institution"],
    "public_holding_pct": ["public", "public holding", "retail", "others"],
    "total_shares":     ["total shares", "paid up shares", "equity shares", "number of shares"],
    "pledged_shares_pct": ["pledged", "pledge %", "pledged shares"],
    "liquidity_gap_30d": ["30 day", "upto 30", "1 month", "0-30", "30 days"],
    "liquidity_gap_90d": ["90 day", "upto 90", "3 month", "0-90", "quarter"],
    "total_portfolio_size": ["total portfolio", "aum", "assets under management", "total loan", "portfolio size"],
    "average_interest_rate": ["average rate", "avg rate", "weighted average", "interest rate", "coupon"],
}

ALM_KEYWORDS = ["asset", "liability", "gap", "maturity", "bucket", "liquidity", "nsfr", "lcr", "outflow", "inflow"]
SHAREHOLDING_KEYWORDS = ["promoter", "holding", "shares", "shareholder", "equity", "stake", "ownership"]
BORROWING_KEYWORDS = ["lender", "bank", "loan", "borrowing", "repayment", "emi", "outstanding", "sanction"]
ANNUAL_KEYWORDS = ["profit", "loss", "revenue", "assets", "liabilities", "balance sheet", "p&l", "cashflow", "income"]
PORTFOLIO_KEYWORDS = ["npa", "stage", "par", "portfolio", "collection", "disbursement", "overdue", "delinquency"]


def clean_value(val):
    """Convert messy Excel values to float."""
    if val is None or (isinstance(val, float) and np.isnan(val)): return None
    if isinstance(val, (int, float)): return float(val)
    s = str(val).strip().replace(",", "").replace("₹", "").replace("$", "").replace("%", "").replace("(", "-").replace(")", "")
    s = re.sub(r"[^\d.\-]", "", s)
    try: return float(s)
    except: return None


def detect_doc_type_from_content(sheets_text: str) -> str:
    """Detect document type from Excel content keywords."""
    text = sheets_text.lower()
    scores = {
        "ALM": sum(1 for k in ALM_KEYWORDS if k in text),
        "Shareholding_Pattern": sum(1 for k in SHAREHOLDING_KEYWORDS if k in text),
        "Borrowing_Profile": sum(1 for k in BORROWING_KEYWORDS if k in text),
        "Annual_Report": sum(1 for k in ANNUAL_KEYWORDS if k in text),
        "Portfolio_Data": sum(1 for k in PORTFOLIO_KEYWORDS if k in text),
    }
    return max(scores, key=scores.get)


def find_header_row(df: pd.DataFrame) -> int:
    """Find the actual header row in messy Excel (may not be row 0)."""
    for i, row in df.iterrows():
        non_null = row.dropna()
        if len(non_null) >= 2:
            # Check if this row looks like headers (has text, not all numbers)
            text_vals = [str(v) for v in non_null if not isinstance(v, (int, float))]
            if len(text_vals) >= 2:
                return i
    return 0


def extract_key_value_pairs(df: pd.DataFrame) -> dict:
    """Extract key-value pairs from 2-column financial tables."""
    result = {}
    for _, row in df.iterrows():
        vals = [v for v in row if pd.notna(v) and str(v).strip()]
        if len(vals) >= 2:
            key = str(vals[0]).strip().lower()
            val = clean_value(vals[-1])  # take last non-null as value
            if val is not None:
                # Match against known financial keywords
                for field, keywords in FINANCIAL_KEYWORDS.items():
                    if any(kw in key for kw in keywords):
                        result[field] = val
                        break
    return result


def extract_table_data(df: pd.DataFrame, schema_fields: list) -> dict:
    """Extract structured data from a DataFrame matching schema fields."""
    result = {}

    # Try key-value extraction first (2-column tables)
    if df.shape[1] <= 3:
        kv = extract_key_value_pairs(df)
        result.update(kv)

    # Try header-based extraction (multi-column tables)
    header_row = find_header_row(df)
    if header_row > 0:
        df = df.iloc[header_row:].reset_index(drop=True)
        df.columns = [str(c).strip().lower() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)

    # Scan all cells for financial data
    for col in df.columns:
        col_lower = str(col).lower()
        for field, keywords in FINANCIAL_KEYWORDS.items():
            if any(kw in col_lower for kw in keywords):
                # Get first non-null numeric value
                for val in df[col]:
                    cleaned = clean_value(val)
                    if cleaned is not None and cleaned != 0:
                        result[field] = cleaned
                        break

    # Filter to only schema fields if specified
    if schema_fields:
        result = {k: v for k, v in result.items() if k in schema_fields}

    return result


def extract_with_gemini(file_path: str, doc_type: str, schema_fields: list) -> dict:
    """Use Gemini to extract from complex Excel when rule-based fails."""
    try:
        # Read all sheets as text
        xl = pd.ExcelFile(file_path)
        all_text = []
        for sheet in xl.sheet_names[:3]:  # max 3 sheets
            df = pd.read_excel(file_path, sheet_name=sheet, header=None)
            all_text.append(f"Sheet: {sheet}\n{df.to_string(max_rows=50, max_cols=10)}")
        content = "\n\n".join(all_text)[:3000]

        prompt = f"""You are a financial data extraction expert for Indian corporate lending.
Extract financial data from this {doc_type} Excel document.

Document content:
{content}

Extract these specific fields: {schema_fields}

Return ONLY a JSON object with the field names as keys and numeric values.
For percentages, return as decimal (e.g., 45.2% = 45.2).
For amounts in lakhs/crores, return the number as shown.
If a field is not found, omit it.

Example: {{"revenue": 9820000, "net_profit": 450000, "current_ratio": 1.4}}"""

        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        clean = re.sub(r"```json|```", "", response.text).strip()
        return json.loads(clean)
    except Exception as e:
        return {}


def extract_from_excel(file_path: str, doc_type: str, schema_fields: list = None) -> dict:
    """
    Main extraction function — handles any Excel file.
    Tries rule-based first, falls back to Gemini.
    """
    if schema_fields is None:
        schema_fields = list(FINANCIAL_KEYWORDS.keys())

    result = {
        "doc_type": doc_type,
        "file": file_path.split("/")[-1],
        "extracted_fields": {},
        "sheets_found": [],
        "extraction_method": "rule_based",
        "raw_tables": {}
    }

    try:
        xl = pd.ExcelFile(file_path)
        result["sheets_found"] = xl.sheet_names

        all_extracted = {}
        sheets_text = ""

        for sheet_name in xl.sheet_names[:5]:  # max 5 sheets
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
                if df.empty: continue

                # Store raw table preview
                result["raw_tables"][sheet_name] = df.head(20).fillna("").to_dict()
                sheets_text += df.to_string(max_rows=30) + " "

                # Extract from this sheet
                sheet_data = extract_table_data(df, schema_fields)
                all_extracted.update(sheet_data)

            except Exception as e:
                continue

        # If rule-based found enough, use it
        if len(all_extracted) >= 3:
            result["extracted_fields"] = all_extracted
            result["extraction_method"] = "rule_based"
        else:
            # Fall back to Gemini
            gemini_data = extract_with_gemini(file_path, doc_type, schema_fields)
            result["extracted_fields"] = {**all_extracted, **gemini_data}
            result["extraction_method"] = "gemini_assisted"

        # Post-process: detect doc type if unknown
        if doc_type == "Unknown":
            result["detected_doc_type"] = detect_doc_type_from_content(sheets_text)

    except Exception as e:
        result["error"] = str(e)
        # Last resort: full Gemini extraction
        gemini_data = extract_with_gemini(file_path, doc_type, schema_fields)
        result["extracted_fields"] = gemini_data
        result["extraction_method"] = "gemini_fallback"

    return result


def extract_from_image(file_path: str, doc_type: str, schema_fields: list = None) -> dict:
    """Extract financial data from image files using Gemini Vision."""
    import base64
    if schema_fields is None:
        schema_fields = list(FINANCIAL_KEYWORDS.keys())
    try:
        with open(file_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        ext = file_path.split(".")[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        prompt = f"""Extract all financial data from this {doc_type} document image.
Fields to extract: {schema_fields}
Return ONLY valid JSON with field names and numeric values."""
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content([
            {"mime_type": mime, "data": image_data},
            prompt
        ])
        clean = re.sub(r"```json|```", "", response.text).strip()
        extracted = json.loads(clean)
        return {"doc_type": doc_type, "extracted_fields": extracted, "extraction_method": "gemini_vision"}
    except Exception as e:
        return {"doc_type": doc_type, "extracted_fields": {}, "error": str(e)}


def smart_extract(file_path: str, doc_type: str, schema_fields: list = None) -> dict:
    """
    Smart router — picks right extractor based on file type.
    This is the main function to call from app.py
    """
    ext = file_path.split(".")[-1].lower()
    if ext in ["xlsx", "xls"]:
        return extract_from_excel(file_path, doc_type, schema_fields)
    elif ext == "csv":
        try:
            df = pd.read_csv(file_path)
            extracted = extract_table_data(df, schema_fields or list(FINANCIAL_KEYWORDS.keys()))
            return {"doc_type": doc_type, "extracted_fields": extracted,
                    "extraction_method": "csv_parser", "raw_tables": {"Sheet1": df.head(20).fillna("").to_dict()}}
        except Exception as e:
            return {"doc_type": doc_type, "extracted_fields": {}, "error": str(e)}
    elif ext in ["jpg", "jpeg", "png"]:
        return extract_from_image(file_path, doc_type, schema_fields)
    else:
        return {"doc_type": doc_type, "extracted_fields": {}, "error": f"Unsupported: {ext}"}


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        result = smart_extract(sys.argv[1], "Annual_Report")
        print(json.dumps(result["extracted_fields"], indent=2))
        print(f"Method: {result['extraction_method']}")
        print(f"Sheets: {result.get('sheets_found', [])}")