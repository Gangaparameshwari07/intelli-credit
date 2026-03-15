# 🏦 Intelli-Credit Engine
### Vivriti Capital × IIT Hyderabad — Yuvaan Hackathon 2026

> **End-to-End AI Credit Underwriting · Raw Documents → Investment Report in < 2 Minutes**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://intelli-credit.streamlit.app/)

---

## 🎯 What It Does

Intelli-Credit Engine automates the entire credit underwriting workflow for B2B lending — transforming raw, unstructured financial documents into a comprehensive, AI-backed Credit Appraisal Memo (CAM) in under 2 minutes.

A process that takes a credit analyst **7 days manually** now takes **under 2 minutes**.

---

## 🚀 Live Demo

**Hosted URL:** https://intelli-credit.streamlit.app

> No VPN required. Accessible globally.

---

## ✨ Key Features

### 1. Entity Onboarding
- Multi-step form capturing CIN, PAN, Sector, Turnover, Promoters
- Loan details: Type, Amount, Tenure, Interest Rate, Collateral
- Sample data loader for quick demo

### 2. Intelligent Document Ingestion
- Upload interface for all 5 critical document types:
  - ALM (Asset Liability Management)
  - Shareholding Pattern
  - Borrowing Profile
  - Annual Reports (P&L, Balance Sheet, Cash Flow)
  - Portfolio Cuts / Performance Data
- Supports PDF, Excel (.xlsx/.xls), CSV, and Images (JPG/PNG)

### 3. Automated Extraction & Schema Mapping
- **Auto-classification** using Gemini AI — reads actual file content, not just filename
- **Human-in-the-loop** — approve, deny, or edit classifications
- **Dynamic schema editor** — configure exactly which fields to extract
- **4-layer extraction pipeline:**
  - Layer 1: Fast regex rule-based (free, instant)
  - Layer 2: pdfplumber table extraction (handles complex tables)
  - Layer 3: Gemini text extraction (deep understanding)
  - Layer 4: Gemini Vision page-by-page (handles scanned PDFs)

### 4. Pre-Cognitive Secondary Analysis
- **Live web research** via Tavily — news, legal filings, market sentiment
- **MCA lookup** — director details, company status, regulatory actions
- **RBI defaulter blacklist check** — PNB, IDBI, BOB, Syndicate Bank lists
- **Five Cs scoring** — Character, Capacity, Capital, Collateral, Conditions
- **LightGBM ML model** — trained on real loan data with SHAP explainability
- **SWOT analysis** — AI-generated, entity-specific
- **Natural Language Explainer** — plain English reasoning for every decision
- **Early Warning System** — flags GST discrepancies, high leverage, blacklist hits
- **Downloadable CAM** — professional Word document investment report

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                    │
│         4-Step Multi-Form · Dark Fintech UI             │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌───────────────┐ ┌──────────┐ ┌──────────────┐
│ Data Ingestor │ │ Research │ │Recommendation│
│               │ │  Agent   │ │   Engine     │
│ • pdf_parser  │ │          │ │              │
│ • excel_extractor│ • Tavily │ │ • LightGBM  │
│ • gst_analyzer│ │ • MCA    │ │ • SHAP       │
│ • blacklist   │ │ • Web    │ │ • Five Cs    │
│ • structured  │ │  crawler │ │ • CAM gen    │
└───────┬───────┘ └────┬─────┘ └──────┬───────┘
        │              │              │
        └──────────────▼──────────────┘
                  Gemini 2.5 Flash
                  (Extraction + SWOT + NLP)
```

---

## 🧠 ML Model Details

- **Model:** LightGBM (Gradient Boosted Trees)
- **Explainability:** SHAP values — shows exactly which features drove the decision
- **Scoring:** Hybrid — 50% rule-based Five Cs + 50% LightGBM
- **Output:** Default probability, ML score, risk factors, positive factors
- **Thresholds:**
  - Score ≥ 70 → APPROVE
  - Score 45–69 → CONDITIONAL APPROVE
  - Score < 45 → REJECT
  - Blacklisted → REJECT (hard override)

---

## 📁 Project Structure

```
intelli-credit/
├── app.py                          # Main Streamlit application
├── config.py                       # API keys (env variables)
├── excel_extractor.py              # Excel/CSV extraction engine
├── gemini_manager.py               # Quota management + fallbacks
├── requirements.txt
├── packages.txt
├── data_ingestor/
│   ├── pdf_parser.py               # Advanced PDF extraction (scanned + digital)
│   ├── excel_extractor.py
│   ├── gst_analyzer.py             # GST-Bank cross verification
│   ├── blacklist_checker.py        # RBI defaulter lists
│   ├── structured_loader.py
│   └── databricks_loader.py
├── research_agent/
│   ├── web_crawler.py              # Tavily research + rate limiting
│   ├── mca_lookup.py               # MCA + eCourts lookup
│   └── qualitative_portal.py
├── recommendation_engine/
│   ├── ml_model.py                 # LightGBM model
│   ├── credit_scorer.py            # Five Cs + decision engine
│   └── cam_generator.py            # Word CAM generation
└── data/
    ├── sample/                     # Sample test files
    └── lightgbm_model.pkl          # Trained model
```

---

## ⚙️ Setup & Run Locally

### Prerequisites
- Python 3.10+
- Node.js (optional, for advanced doc generation)

### Installation

```bash
git clone https://github.com/Gangaparameshwari07/intelli-credit.git
cd intelli-credit
pip install -r requirements.txt
```

### API Keys

Create `.streamlit/secrets.toml`:
```toml
GEMINI_API_KEY = "your_gemini_api_key"
TAVILY_API_KEY = "your_tavily_api_key"
```

Get keys from:
- Gemini: https://aistudio.google.com
- Tavily: https://tavily.com

### Run

```bash
streamlit run app.py
```

---

## 🌐 Deploy to Streamlit Cloud

1. Fork this repo
2. Go to share.streamlit.io
3. New app → select repo → `app.py`
4. Advanced settings → paste secrets
5. Deploy

---

## 📊 Evaluation Criteria Coverage

| Criteria | Implementation | Status |
|---|---|---|
| Operational Excellence | Stable 4-step form, quota protection, error handling | ✅ |
| Extraction Accuracy | 4-layer pipeline: regex + pdfplumber + Gemini text + Gemini Vision | ✅ |
| Analytical Depth | Live research + MCA + blacklist + SHAP + Five Cs + SWOT | ✅ |
| User Experience | Dark fintech UI, progress tracker, NL explainer, CAM download | ✅ |

---

## 🔑 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit + Custom CSS |
| AI/LLM | Google Gemini 2.5 Flash |
| ML Model | LightGBM + SHAP |
| Research | Tavily Search API |
| PDF Extraction | pdfplumber + Gemini Vision |
| Excel Extraction | openpyxl + xlrd + Gemini |
| Document Generation | python-docx |
| Visualization | Plotly |

---

## ⚠️ Production Notes

The following features use Mock API Gateways in this prototype — production versions would integrate with:

| Mock | Production Integration |
|---|---|
| GSTN cross-verification | GSTN Sandbox API (RBI-licensed) |
| eCourts lookup | eCourts India REST API |
| CIBIL check | Equifax / CIBIL commercial API |
| MCA filings | mca.gov.in REST API |

The AI pipeline (extraction, scoring, SHAP, SWOT) is **fully production-ready** today.

---

## 👥 Team

Built for the **Vivriti Capital "Intelli-Credit" Challenge** at IIT Hyderabad — Yuvaan Hackathon 2026

---

## 📄 License

MIT License — Built for hackathon purposes.
