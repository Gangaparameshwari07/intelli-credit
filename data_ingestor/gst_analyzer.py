import pandas as pd
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)


def load_gst_data(filepath) -> pd.DataFrame:
    return pd.read_csv(filepath)


def load_bank_statement(filepath) -> pd.DataFrame:
    return pd.read_csv(filepath)


def cross_verify(gst_df: pd.DataFrame, bank_df: pd.DataFrame) -> dict:
    # Real production fix - flexible column detection
    taxable_col = next((c for c in gst_df.columns 
        if "taxable" in c.lower() or "value" in c.lower()), 
        gst_df.columns[2])
    gst_revenue = gst_df[taxable_col].sum()
    
    type_col = next((c for c in bank_df.columns 
        if "type" in c.lower() or "txn" in c.lower()), None)
    amt_col = next((c for c in bank_df.columns 
        if "amount" in c.lower() or "amt" in c.lower()), None)
    if type_col and amt_col:
        bank_credits = bank_df[bank_df[type_col].str.lower().str.contains("credit", na=False)][amt_col].sum()
    else:
        bank_credits = 0

    discrepancy = abs(gst_revenue - bank_credits)
    discrepancy_pct = (discrepancy / bank_credits) * 100 if bank_credits else 0

    flags = []
    if discrepancy_pct > 20:
        flags.append(f"Revenue mismatch of {discrepancy_pct:.1f}% between GST and bank statement")
    if discrepancy_pct > 40:
        flags.append("High risk: Possible circular trading or revenue inflation detected")

    return {
        "gst_revenue": gst_revenue,
        "bank_credits": bank_credits,
        "discrepancy_pct": round(discrepancy_pct, 2),
        "flags": flags,
        "risk_level": "high" if discrepancy_pct > 40 else "medium" if discrepancy_pct > 20 else "low"
    }


def gstr_2a_vs_3b_reconciliation(gst_df: pd.DataFrame) -> dict:
    """
    GSTR-2A = auto-populated from supplier invoices (what suppliers say they sold you)
    GSTR-3B = self-declared by company (what company claims as Input Tax Credit)
    Mismatch = possible ITC fraud
    """
    reconciliation = {
        "gstr_3b_itc_claimed": 0,
        "gstr_2a_itc_available": 0,
        "itc_variance": 0,
        "itc_variance_pct": 0,
        "flags": [],
        "risk_level": "low"
    }

    try:
        if "return_type" in gst_df.columns:
            gstr_3b = gst_df[gst_df["return_type"] == "GSTR3B"]
            gstr_2a = gst_df[gst_df["return_type"] == "GSTR2A"]

            itc_3b = gstr_3b["total_tax"].sum() if "total_tax" in gstr_3b.columns else 0
            itc_2a = gstr_2a["total_tax"].sum() if "total_tax" in gstr_2a.columns else 0

            if itc_2a > 0:
                variance = abs(itc_3b - itc_2a)
                variance_pct = (variance / itc_2a) * 100

                reconciliation["gstr_3b_itc_claimed"] = round(itc_3b, 2)
                reconciliation["gstr_2a_itc_available"] = round(itc_2a, 2)
                reconciliation["itc_variance"] = round(variance, 2)
                reconciliation["itc_variance_pct"] = round(variance_pct, 2)

                if variance_pct > 20:
                    reconciliation["flags"].append(
                        f"ITC mismatch of {variance_pct:.1f}% — company claiming more credit than suppliers reported"
                    )
                    reconciliation["risk_level"] = "medium"
                if variance_pct > 40:
                    reconciliation["flags"].append(
                        "HIGH RISK: Severe GSTR-2A vs 3B mismatch — possible fake ITC claims or supplier collusion"
                    )
                    reconciliation["risk_level"] = "high"
            else:
                reconciliation["flags"].append(
                    "Only GSTR-3B data available — GSTR-2A reconciliation not possible"
                )
        else:
            reconciliation["flags"].append(
                "GST data does not contain return_type column — upload GSTR data with both 2A and 3B returns"
            )

    except Exception as e:
        reconciliation["flags"].append(f"Reconciliation error: {str(e)}")

    return reconciliation


def get_gst_insights(gst_df: pd.DataFrame) -> str:
    summary = gst_df.describe().to_string()
    prompt = f"""
    You are a senior Indian credit analyst with deep knowledge of GST filings.
    Analyze this GSTR data and identify:
    1. Revenue trends
    2. GSTR-3B vs GSTR-2A mismatches if visible
    3. Seasonal patterns
    4. Any anomalies suggesting tax evasion or circular trading
    5. Overall business health from GST perspective

    Data: {summary}

    Be specific to Indian GST context. Respond in structured points.
    """
    response = model.generate_content(prompt)
    return response.text