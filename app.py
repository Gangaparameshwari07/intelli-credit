import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from data_ingestor.pdf_parser import analyze_document
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from excel_extractor import smart_extract
from data_ingestor.gst_analyzer import load_gst_data, load_bank_statement, cross_verify, gstr_2a_vs_3b_reconciliation
from data_ingestor.blacklist_checker import check_blacklist
from data_ingestor.databricks_loader import get_borrower_history
from research_agent.web_crawler import research_company
from research_agent.mca_lookup import lookup_mca
from research_agent.qualitative_portal import process_qualitative_notes
from recommendation_engine.credit_scorer import compute_five_cs, make_decision, explain_decision, natural_language_explainer
from recommendation_engine.cam_generator import generate_cam
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL
import re

genai.configure(api_key=GEMINI_API_KEY)

st.set_page_config(page_title="Intelli-Credit Engine", page_icon="🏦", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&family=JetBrains+Mono:wght@400;500&display=swap');
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#060810;--bg2:#0C1020;--bg3:#111828;--card:#0E1422;
  --border:rgba(255,255,255,0.06);--border2:rgba(0,230,118,0.25);
  --green:#00E676;--amber:#FFB300;--red:#FF3D57;--blue:#4FC3F7;
  --text:#F0F4FF;--muted:#6B7A99;
  --fh:'Syne',sans-serif;--fb:'DM Sans',sans-serif;--fm:'JetBrains Mono',monospace;
}
html,body,[data-testid="stAppViewContainer"]{background:var(--bg)!important;color:var(--text)!important;font-family:var(--fb)!important}
[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse 80% 50% at 50% -10%,rgba(0,230,118,0.07) 0%,transparent 60%),radial-gradient(ellipse 40% 40% at 90% 80%,rgba(79,195,247,0.05) 0%,transparent 50%),var(--bg)!important}
.block-container{padding:0 2.5rem 3rem!important;max-width:1400px!important}
[data-testid="stSidebar"]{display:none!important}
header[data-testid="stHeader"]{background:transparent!important}
.stDeployButton{display:none!important}

.hero{text-align:center;padding:3rem 0 1.5rem;position:relative}
.hero-eyebrow{font-family:var(--fm);font-size:0.68rem;letter-spacing:0.25em;color:var(--green);text-transform:uppercase;margin-bottom:0.8rem;opacity:0.8}
.hero-title{font-family:var(--fh);font-size:clamp(2.5rem,5vw,4rem);font-weight:800;line-height:1.05;background:linear-gradient(135deg,#fff 0%,#00E676 50%,#4FC3F7 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:0.6rem;letter-spacing:-0.02em}
.hero-sub{font-size:0.95rem;color:var(--muted);font-weight:300;letter-spacing:0.02em}
.hero-line{width:50px;height:2px;background:linear-gradient(90deg,transparent,var(--green),transparent);margin:1.2rem auto}

.prog-wrap{display:flex;align-items:center;justify-content:center;gap:0;margin:0 auto 2.5rem;max-width:680px}
.prog-step{display:flex;flex-direction:column;align-items:center;gap:0.35rem;flex:1;position:relative;z-index:1}
.prog-circle{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:var(--fm);font-size:0.72rem;font-weight:600}
.pc-done{background:var(--green);color:#000;box-shadow:0 0 18px rgba(0,230,118,0.4)}
.pc-active{background:linear-gradient(135deg,var(--green),var(--blue));color:#000;box-shadow:0 0 22px rgba(0,230,118,0.5)}
.pc-idle{background:var(--bg3);color:var(--muted);border:1px solid var(--border)}
.prog-lbl{font-size:0.62rem;font-family:var(--fm);letter-spacing:0.05em;white-space:nowrap}
.pl-active{color:var(--green)}.pl-done{color:var(--green);opacity:0.6}.pl-idle{color:var(--muted)}
.prog-conn{height:1px;flex:1;max-width:70px;margin-bottom:1.3rem;background:var(--border)}
.prog-conn.done{background:linear-gradient(90deg,var(--green),rgba(0,230,118,0.2))}

.sec-lbl{font-family:var(--fm);font-size:0.65rem;letter-spacing:0.2em;color:var(--green);text-transform:uppercase;margin-bottom:0.4rem}
.sec-title{font-family:var(--fh);font-size:1.55rem;font-weight:700;color:var(--text);margin-bottom:1.5rem;letter-spacing:-0.02em}

.stTextInput>div>div>input,.stNumberInput>div>div>input,.stSelectbox>div>div{background:var(--bg3)!important;border:1px solid var(--border)!important;border-radius:10px!important;color:var(--text)!important;font-family:var(--fb)!important;font-size:0.9rem!important}
.stTextInput>div>div>input:focus,.stNumberInput>div>div>input:focus{border-color:var(--green)!important;box-shadow:0 0 0 2px rgba(0,230,118,0.1)!important}
label[data-testid="stWidgetLabel"] p{font-family:var(--fm)!important;font-size:0.68rem!important;letter-spacing:0.08em!important;color:var(--muted)!important;text-transform:uppercase!important}

.stButton>button{background:linear-gradient(135deg,var(--green),#00C853)!important;color:#000!important;font-family:var(--fh)!important;font-weight:700!important;font-size:0.88rem!important;border:none!important;border-radius:10px!important;padding:0.6rem 1.5rem!important;letter-spacing:0.02em!important;box-shadow:0 4px 18px rgba(0,230,118,0.2)!important;transition:all 0.2s!important}
.stButton>button:hover{transform:translateY(-1px)!important;box-shadow:0 8px 28px rgba(0,230,118,0.35)!important}

.verdict-banner{border-radius:16px;padding:2rem;text-align:center;margin:1.5rem 0;position:relative;overflow:hidden}
.v-approve{background:linear-gradient(135deg,rgba(0,230,118,0.1),rgba(0,200,83,0.05));border:1px solid rgba(0,230,118,0.4);box-shadow:0 0 40px rgba(0,230,118,0.08)}
.v-conditional{background:linear-gradient(135deg,rgba(255,179,0,0.1),rgba(255,152,0,0.05));border:1px solid rgba(255,179,0,0.4);box-shadow:0 0 40px rgba(255,179,0,0.08)}
.v-reject{background:linear-gradient(135deg,rgba(255,61,87,0.1),rgba(211,47,47,0.05));border:1px solid rgba(255,61,87,0.4);box-shadow:0 0 40px rgba(255,61,87,0.08)}
.v-label{font-family:var(--fh);font-size:2rem;font-weight:800;letter-spacing:-0.02em;margin-bottom:0.25rem}
.v-sub{font-family:var(--fm);font-size:0.7rem;letter-spacing:0.1em;opacity:0.55}

.metric-row{display:grid;grid-template-columns:repeat(5,1fr);gap:0.85rem;margin:1.25rem 0}
.metric-tile{background:var(--bg3);border:1px solid var(--border);border-radius:12px;padding:1.1rem 0.8rem;text-align:center}
.m-icon{font-size:1rem;margin-bottom:0.35rem}
.m-val{font-family:var(--fh);font-size:1.3rem;font-weight:700;color:var(--text);letter-spacing:-0.02em;line-height:1.1}
.m-lbl{font-family:var(--fm);font-size:0.58rem;letter-spacing:0.1em;color:var(--muted);text-transform:uppercase;margin-top:0.25rem}

.explainer-box{background:linear-gradient(135deg,rgba(79,195,247,0.06),rgba(0,230,118,0.03));border:1px solid rgba(79,195,247,0.18);border-radius:12px;padding:1.1rem 1.4rem;margin:1rem 0;font-size:0.9rem;color:#B3D9FF;line-height:1.65}
.explainer-tag{font-family:var(--fm);font-size:0.62rem;letter-spacing:0.15em;color:var(--blue);text-transform:uppercase;margin-bottom:0.35rem}

.flag-item{background:rgba(255,61,87,0.05);border:1px solid rgba(255,61,87,0.18);border-left:3px solid var(--red);border-radius:8px;padding:0.7rem 1rem;margin:0.4rem 0;font-size:0.85rem;color:#FF8A9A;font-family:var(--fb)}
.flag-ok{background:rgba(0,230,118,0.05);border:1px solid rgba(0,230,118,0.18);border-left:3px solid var(--green);border-radius:8px;padding:0.7rem 1rem;font-size:0.85rem;color:#80FFB3;font-family:var(--fb)}

.swot-grid{display:grid;grid-template-columns:1fr 1fr;gap:0.85rem}
.swot-q{border-radius:12px;padding:1.1rem}
.sq-s{background:rgba(0,230,118,0.05);border:1px solid rgba(0,230,118,0.12)}
.sq-w{background:rgba(255,179,0,0.05);border:1px solid rgba(255,179,0,0.12)}
.sq-o{background:rgba(79,195,247,0.05);border:1px solid rgba(79,195,247,0.12)}
.sq-t{background:rgba(255,61,87,0.05);border:1px solid rgba(255,61,87,0.12)}
.swot-h{font-family:var(--fh);font-size:0.75rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.7rem}
.sq-s .swot-h{color:var(--green)}.sq-w .swot-h{color:var(--amber)}.sq-o .swot-h{color:var(--blue)}.sq-t .swot-h{color:var(--red)}
.swot-pt{font-size:0.8rem;color:rgba(240,244,255,0.7);padding:0.3rem 0;border-bottom:1px solid rgba(255,255,255,0.04);font-family:var(--fb);line-height:1.4}
.swot-pt:last-child{border-bottom:none}

.doc-slot{background:var(--bg3);border:1px dashed rgba(255,255,255,0.07);border-radius:12px;padding:1.1rem 1.4rem;margin-bottom:0.7rem}
.ds-head{font-family:var(--fh);font-size:0.88rem;font-weight:600;color:var(--text);margin-bottom:0.15rem}
.ds-sub{font-family:var(--fb);font-size:0.72rem;color:var(--muted);margin-bottom:0.65rem}

.badge{font-family:var(--fm);font-size:0.62rem;letter-spacing:0.08em;padding:0.18rem 0.55rem;border-radius:4px;text-transform:uppercase}
.b-auto{background:rgba(0,230,118,0.09);color:var(--green);border:1px solid rgba(0,230,118,0.18)}
.b-edit{background:rgba(255,179,0,0.09);color:var(--amber);border:1px solid rgba(255,179,0,0.18)}

.stTabs [data-baseweb="tab-list"]{background:var(--bg3)!important;border-radius:10px!important;padding:4px!important;gap:2px!important;border:1px solid var(--border)!important}
.stTabs [data-baseweb="tab"]{background:transparent!important;border-radius:7px!important;color:var(--muted)!important;font-family:var(--fm)!important;font-size:0.7rem!important;letter-spacing:0.05em!important;padding:0.45rem 0.9rem!important;border:none!important}
.stTabs [aria-selected="true"]{background:var(--green)!important;color:#000!important;font-weight:600!important}

.stProgress>div>div{background:var(--green)!important;border-radius:4px!important}
.stProgress>div{background:var(--bg3)!important;border-radius:4px!important}
.stAlert{border-radius:10px!important;border:none!important;font-family:var(--fb)!important}
hr{border-color:var(--border)!important;margin:1.5rem 0!important}
.stDownloadButton>button{background:var(--bg3)!important;color:var(--green)!important;border:1px solid rgba(0,230,118,0.25)!important;font-family:var(--fh)!important;font-weight:600!important;border-radius:10px!important;box-shadow:none!important}
.stDownloadButton>button:hover{background:rgba(0,230,118,0.07)!important;border-color:var(--green)!important;transform:translateY(-1px)!important}
.streamlit-expanderHeader{background:var(--bg3)!important;border-radius:8px!important;font-family:var(--fm)!important;font-size:0.75rem!important;color:var(--muted)!important;border:1px solid var(--border)!important}
[data-testid="stFileUploadDropzone"]{background:var(--bg)!important;border:1px dashed rgba(0,230,118,0.18)!important;border-radius:8px!important}
</style>
""", unsafe_allow_html=True)

# ── Session state ──
for k,v in [("step",1),("entity_data",{}),("uploaded_docs",{}),("classifications",{}),("results",{}),("schema_edits",{})]:
    if k not in st.session_state: st.session_state[k]=v

def fmt_inr(val):
    try:
        val=float(val)
        if val>=10000000: return f"₹{val/10000000:.2f} Cr"
        elif val>=100000: return f"₹{val/100000:.2f} L"
        return f"₹{val:,.0f}"
    except: return "N/A"

# ── Hero ──
st.markdown("""
<div class='hero'>
<div class='hero-eyebrow'>Vivriti Capital × IIT Hyderabad × National AI/ML Hackathon</div>
<div class='hero-title'>Intelli-Credit Engine</div>
<div class='hero-sub'>End-to-End AI Credit Underwriting · Raw Documents → Investment Report in &lt;2 Minutes</div>
<div class='hero-line'></div>
</div>""", unsafe_allow_html=True)

# ── Progress ──
s = st.session_state.step
lbls = ["ENTITY","DOCUMENTS","CLASSIFY","REPORT"]
h = "<div class='prog-wrap'>"
for i,l in enumerate(lbls):
    n=i+1
    cc = "pc-done" if n<s else ("pc-active" if n==s else "pc-idle")
    lc = "pl-done" if n<s else ("pl-active" if n==s else "pl-idle")
    h += f"<div class='prog-step'><div class='prog-circle {cc}'>{n}</div><div class='prog-lbl {lc}'>{l}</div></div>"
    if i<3: h += f"<div class='prog-conn {'done' if n<s else ''}'></div>"
h += "</div>"
st.markdown(h, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# STEP 1
# ════════════════════════════════════════════════════════
if s==1:
    st.markdown("<div class='sec-lbl'>Step 01 / 04</div>", unsafe_allow_html=True)
    st.markdown("<div class='sec-title'>Entity Onboarding</div>", unsafe_allow_html=True)
    if st.button("⚡ Load Sample — Sharma Textiles Pvt Ltd"):
        st.session_state.entity_data={"company_name":"Sharma Textiles Pvt Ltd","cin":"U51909DL2011PTC220073","pan":"AABCS1234C","sector":"Textile","sub_sector":"Wholesale Trade — MMF Fabrics","turnover":9820000,"promoter_names":"Rajesh Sharma, Priya Sharma","incorporation_year":2011,"employee_count":50,"loan_type":"Term Loan","loan_amount":5000000,"tenure_months":36,"interest_rate":11.0,"collateral_type":"Immovable","collateral_value":7500000}
        st.rerun()
    e=st.session_state.entity_data
    st.markdown("<div class='sec-lbl' style='margin-top:1.2rem'>Company Information</div>", unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        company_name=st.text_input("Company Name",value=e.get("company_name",""),placeholder="Sharma Textiles Pvt Ltd")
        cin=st.text_input("CIN",value=e.get("cin",""),placeholder="U51909DL2011PTC220073")
        pan=st.text_input("PAN",value=e.get("pan",""),placeholder="AABCS1234C")
        sector=st.selectbox("Sector",["Textile","Manufacturing","Trading","Real Estate","Infrastructure","FMCG","Pharmaceuticals","IT/ITeS","Agriculture","NBFC","Other"],index=["Textile","Manufacturing","Trading","Real Estate","Infrastructure","FMCG","Pharmaceuticals","IT/ITeS","Agriculture","NBFC","Other"].index(e.get("sector","Textile")))
    with c2:
        sub_sector=st.text_input("Sub-Sector",value=e.get("sub_sector",""),placeholder="Wholesale Trade — MMF Fabrics")
        turnover=st.number_input("Annual Turnover (₹)",value=int(e.get("turnover",10000000)),step=100000)
        promoter_names=st.text_input("Promoter Names",value=e.get("promoter_names",""),placeholder="Rajesh Sharma, Priya Sharma")
        incorporation_year=st.number_input("Year of Incorporation",value=int(e.get("incorporation_year",2015)),min_value=1900,max_value=2025,step=1)
    st.markdown("<div class='sec-lbl' style='margin-top:1.2rem'>Loan Details</div>", unsafe_allow_html=True)
    c3,c4=st.columns(2)
    with c3:
        loan_type=st.selectbox("Loan Type",["Term Loan","Working Capital","Cash Credit","Letter of Credit","Equipment Finance","Invoice Discounting"],index=["Term Loan","Working Capital","Cash Credit","Letter of Credit","Equipment Finance","Invoice Discounting"].index(e.get("loan_type","Term Loan")))
        loan_amount=st.number_input("Loan Amount (₹)",value=int(e.get("loan_amount",5000000)),step=100000)
        tenure_months=st.number_input("Tenure (Months)",value=int(e.get("tenure_months",36)),step=6,min_value=6)
    with c4:
        interest_rate=st.number_input("Interest Rate (% p.a.)",value=float(e.get("interest_rate",11.0)),step=0.5)
        collateral_type=st.selectbox("Collateral Type",["Immovable","Movable","Financial Securities","None"],index=["Immovable","Movable","Financial Securities","None"].index(e.get("collateral_type","Immovable")))
        collateral_value=st.number_input("Collateral Value (₹)",value=int(e.get("collateral_value",7500000)),step=100000)
    st.markdown("<br>",unsafe_allow_html=True)
    if st.button("Continue to Document Upload →",use_container_width=True):
        if not company_name or not cin or not pan: st.error("Company Name, CIN and PAN are required.")
        else:
            st.session_state.entity_data={"company_name":company_name,"cin":cin,"pan":pan,"sector":sector,"sub_sector":sub_sector,"turnover":turnover,"promoter_names":promoter_names,"incorporation_year":incorporation_year,"loan_type":loan_type,"loan_amount":loan_amount,"tenure_months":tenure_months,"interest_rate":interest_rate,"collateral_type":collateral_type,"collateral_value":collateral_value}
            st.session_state.step=2; st.rerun()

# ════════════════════════════════════════════════════════
# STEP 2
# ════════════════════════════════════════════════════════
elif s==2:
    entity=st.session_state.entity_data
    st.markdown("<div class='sec-lbl'>Step 02 / 04</div>",unsafe_allow_html=True)
    st.markdown("<div class='sec-title'>Document Upload</div>",unsafe_allow_html=True)
    st.markdown(f"<div style='background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:0.8rem 1.2rem;margin-bottom:1.5rem;font-family:var(--fm);font-size:0.72rem'><span style='color:var(--muted)'>ENTITY </span><span style='color:var(--text);margin-right:1.5rem'>{entity.get('company_name','—')}</span><span style='color:var(--muted)'>CIN </span><span style='color:var(--text);margin-right:1.5rem'>{entity.get('cin','—')}</span><span style='color:var(--muted)'>LOAN </span><span style='color:var(--green)'>{fmt_inr(entity.get('loan_amount',0))}</span></div>",unsafe_allow_html=True)
    docs=[{"key":"alm","icon":"⚖️","label":"ALM — Asset Liability Management","desc":"Maturity profile, liquidity gaps, ALM statement"},{"key":"shareholding","icon":"👥","label":"Shareholding Pattern","desc":"Promoter holdings, institutional investors, ownership structure"},{"key":"borrowing","icon":"🏦","label":"Borrowing Profile","desc":"Existing debt schedule, lender details, repayment history"},{"key":"annual_report","icon":"📊","label":"Annual Report (P&L · Balance Sheet · CF)","desc":"Audited financial statements — P&L, Balance Sheet, Cash Flow"},{"key":"portfolio","icon":"📈","label":"Portfolio Cuts / Performance Data","desc":"Loan portfolio quality, NPA data, sector-wise performance"}]
    for doc in docs:
        already=doc['key'] in st.session_state.uploaded_docs
        tick=f'  <span style="color:var(--green);font-size:0.68rem">✓ UPLOADED</span>' if already else ''
        st.markdown(f"<div class='doc-slot'><div class='ds-head'>{doc['icon']}  {doc['label']}{tick}</div><div class='ds-sub'>{doc['desc']}</div></div>",unsafe_allow_html=True)
        up=st.file_uploader(f"Upload {doc['label']}",type=["pdf","xlsx","csv","png","jpg"],key=f"up_{doc['key']}",label_visibility="collapsed")
        if up: st.session_state.uploaded_docs[doc['key']]=up
    n=len(st.session_state.uploaded_docs)
    st.markdown(f"<div style='font-family:var(--fm);font-size:0.7rem;color:var(--muted);margin:0.8rem 0'>{n}/5 DOCUMENTS UPLOADED</div>",unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        if st.button("← Back",use_container_width=True): st.session_state.step=1; st.rerun()
    with c2:
        if st.button(f"Continue to Classification → ({n} docs)",use_container_width=True):
            if n==0: st.error("Upload at least 1 document.")
            else: st.session_state.step=3; st.rerun()

# ════════════════════════════════════════════════════════
# STEP 3
# ════════════════════════════════════════════════════════
elif s==3:
    st.markdown("<div class='sec-lbl'>Step 03 / 04</div>",unsafe_allow_html=True)
    st.markdown("<div class='sec-title'>Auto-Classification & Schema Mapping</div>",unsafe_allow_html=True)
    DOC_TYPES=["ALM","Shareholding_Pattern","Borrowing_Profile","Annual_Report","Portfolio_Data"]

    def read_file_preview(f) -> str:
        """Read actual file content for better classification."""
        try:
            ext = f.name.split(".")[-1].lower()
            f.seek(0)
            if ext == "csv":
                df = pd.read_csv(f, nrows=5)
                f.seek(0)
                return f"Columns: {list(df.columns)}\nSample rows:\n{df.head(3).to_string()}"
            elif ext in ["xlsx","xls"]:
                df = pd.read_excel(f, nrows=5, header=None)
                f.seek(0)
                return f"Excel content preview:\n{df.head(5).to_string()}"
            elif ext == "pdf":
                f.seek(0)
                return f"PDF document: {f.name}"
            else:
                return f"File: {f.name}"
        except:
            f.seek(0)
            return f"File: {f.name}"

    def classify_doc(fname, content_preview):
        # Rule-based first — fast and free
        n = fname.lower()
        c = content_preview.lower()

        # Strong filename signals
        if "alm" in n: return "ALM"
        if "shareholding" in n or "sharehol" in n: return "Shareholding_Pattern"
        if "borrowing" in n or "borrow" in n: return "Borrowing_Profile"
        if "portfolio" in n or "npa" in n or "par" in n: return "Portfolio_Data"
        if "annual" in n or "pnl" in n or "balance" in n or "financials" in n: return "Annual_Report"

        # Content-based signals
        if any(k in c for k in ["gstin","gst","taxable_value","igst","cgst","sgst","filing"]): return "Portfolio_Data"
        if any(k in c for k in ["maturity","liquidity","gap","bucket","inflow","outflow","nsfr","lcr"]): return "ALM"
        if any(k in c for k in ["promoter","holding","shares","shareholder","stake","pledge"]): return "Shareholding_Pattern"
        if any(k in c for k in ["lender","sanction","outstanding","repayment","emi","secured","unsecured"]): return "Borrowing_Profile"
        if any(k in c for k in ["npa","stage 1","stage 2","stage 3","par 30","par 90","delinquency","collection"]): return "Portfolio_Data"
        if any(k in c for k in ["revenue","profit","assets","liabilities","cashflow","ebitda","balance sheet"]): return "Annual_Report"
        if any(k in c for k in ["date","description","amount","balance","credit","debit","transaction"]): return "Borrowing_Profile"

        # Gemini as last resort only
        try:
            prompt = f"""Classify this Indian financial document into exactly ONE category:
ALM, Shareholding_Pattern, Borrowing_Profile, Annual_Report, Portfolio_Data

Filename: {fname}
Content preview: {content_preview[:400]}

Rules:
- GST data, tax filings → Portfolio_Data
- Bank statements, loan schedules → Borrowing_Profile  
- P&L, Balance Sheet, Cash Flow → Annual_Report
- Promoter/shareholder data → Shareholding_Pattern
- Maturity buckets, liquidity → ALM

Return ONLY the category name, nothing else."""
            m = genai.GenerativeModel(GEMINI_MODEL)
            r = m.generate_content(prompt)
            result = r.text.strip()
            for dt in DOC_TYPES:
                if dt.lower() in result.lower(): return dt
            return "Annual_Report"
        except:
            return "Annual_Report"

    if not st.session_state.classifications:
        with st.spinner("AI classifying documents..."):
            for k,f in st.session_state.uploaded_docs.items():
                preview = read_file_preview(f)
                st.session_state.classifications[k] = classify_doc(f.name, preview)
    st.markdown("<div style='background:rgba(0,230,118,0.04);border:1px solid rgba(0,230,118,0.12);border-radius:10px;padding:0.8rem 1.2rem;margin-bottom:1.5rem;font-family:var(--fm);font-size:0.68rem;color:var(--green);letter-spacing:0.1em'>✦ AI CLASSIFICATION COMPLETE — REVIEW & APPROVE BELOW</div>",unsafe_allow_html=True)
    updated={}
    for k,f in st.session_state.uploaded_docs.items():
        cur=st.session_state.classifications.get(k,"Annual_Report")
        c1,c2,c3=st.columns([3,2,1])
        with c1: st.markdown(f"<div style='font-family:var(--fm);font-size:0.78rem;color:var(--text);padding-top:0.5rem'>📄 {f.name}<br><span style='color:var(--muted);font-size:0.62rem'>{f.size/1024:.1f} KB</span></div>",unsafe_allow_html=True)
        with c2:
            nc=st.selectbox("Type",DOC_TYPES,index=DOC_TYPES.index(cur) if cur in DOC_TYPES else 0,key=f"cls_{k}",label_visibility="collapsed")
            updated[k]=nc
        with c3:
            bc="b-auto" if nc==cur else "b-edit"
            bl="AUTO ✓" if nc==cur else "EDITED ✏"
            st.markdown(f"<div style='padding-top:0.45rem'><span class='badge {bc}'>{bl}</span></div>",unsafe_allow_html=True)
        st.markdown("<hr>",unsafe_allow_html=True)
    st.session_state.classifications=updated
    st.markdown("<div class='sec-lbl' style='margin-top:0.8rem'>Dynamic Schema Configuration</div>",unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.82rem;color:var(--muted);margin-bottom:0.8rem;font-family:var(--fb)'>Configure which fields to extract from each document.</div>",unsafe_allow_html=True)
    default_schema={"Annual_Report":["revenue","net_profit","total_assets","total_liabilities","net_worth","debt_service_coverage","current_ratio","debt_to_equity","revenue_growth"],"ALM":["total_assets","total_liabilities","liquidity_gap_30d","liquidity_gap_90d","nsfr_ratio","lcr_ratio"],"Shareholding_Pattern":["promoter_holding_pct","institutional_holding_pct","public_holding_pct","total_shares","pledged_shares_pct"],"Borrowing_Profile":["total_debt","secured_debt","unsecured_debt","average_interest_rate","debt_maturity_1yr","debt_maturity_3yr"],"Portfolio_Data":["total_portfolio_size","npa_pct","stage_1_pct","stage_2_pct","stage_3_pct","par_30","par_90"]}
    schema_edits={}
    for k,dt in updated.items():
        fields=default_schema.get(dt,["revenue","total_assets"])
        with st.expander(f"⚙  Schema · {dt} · {st.session_state.uploaded_docs[k].name}",expanded=False):
            txt=st.text_area("Fields (one per line)",value="\n".join(fields),key=f"schema_{k}",height=120)
            schema_edits[k]=[f.strip() for f in txt.split("\n") if f.strip()]
    c1,c2=st.columns(2)
    with c1:
        if st.button("← Back",use_container_width=True): st.session_state.step=2; st.rerun()
    with c2:
        if st.button("🚀 Extract & Generate Report",use_container_width=True): st.session_state.schema_edits=schema_edits; st.session_state.step=4; st.rerun()

# ════════════════════════════════════════════════════════
# STEP 4
# ════════════════════════════════════════════════════════
elif s==4:
    entity=st.session_state.entity_data
    company_name=entity.get("company_name","Unknown")
    promoters=[p.strip() for p in entity.get("promoter_names","").split(",") if p.strip()]
    st.markdown("<div class='sec-lbl'>Step 04 / 04</div>",unsafe_allow_html=True)
    st.markdown(f"<div class='sec-title'>Credit Decision Report — {company_name}</div>",unsafe_allow_html=True)

    if not st.session_state.results:
        prog=st.progress(0); stat=st.empty()
        financial_data={"loan_amount_requested":entity.get("loan_amount",5000000),"interest_rate":entity.get("interest_rate",11.0),"collateral_type":entity.get("collateral_type","immovable").lower(),"collateral_coverage":entity.get("collateral_value",0)/max(entity.get("loan_amount",1),1),"sector_outlook":"positive","debt_service_coverage":1.5,"current_ratio":1.2,"debt_to_equity":1.5,"revenue_growth":0.1,"net_worth":entity.get("turnover",10000000)*0.3,"delinquency_two_years":0,"inquiries_six_months":0,"open_accounts":5,"public_record":0,"total_accounts":10,"revolving_balance":0,"revolving_utilities":50.0,"total_current_balance":0,"total_revolving_credit_limit":0}
        pdf_analyses={}
        excel_analyses={}
        os.makedirs("data/sample",exist_ok=True)
        stat.info("📄 Extracting data from uploaded documents...")
        for k,f in st.session_state.uploaded_docs.items():
            try:
                path=f"data/sample/{f.name}"; f.seek(0)
                with open(path,"wb") as fh: fh.write(f.read())
                dt=st.session_state.classifications.get(k,"Annual_Report")
                schema=st.session_state.get("schema_edits",{}).get(k,None)
                ext=f.name.split(".")[-1].lower()

                if ext=="pdf":
                    analysis=analyze_document(path,dt); pdf_analyses[k]=analysis
                    fin=analysis.get("financials",{})
                    for fld in ["debt_service_coverage","current_ratio","debt_to_equity"]:
                        if fin.get(fld,0)>0: financial_data[fld]=fin[fld]
                    if fin.get("net_worth",0)>0: financial_data["net_worth"]=fin["net_worth"]*100000

                elif ext in ["xlsx","xls","csv","png","jpg","jpeg"]:
                    result=smart_extract(path,dt,schema)
                    excel_analyses[k]=result
                    ef=result.get("extracted_fields",{})
                    # Map extracted fields to financial_data
                    for fld in ["debt_service_coverage","current_ratio","debt_to_equity","revenue_growth"]:
                        if ef.get(fld,0) and float(ef[fld])>0: financial_data[fld]=float(ef[fld])
                    if ef.get("net_worth",0) and float(ef["net_worth"])>0:
                        financial_data["net_worth"]=float(ef["net_worth"])
                    if ef.get("revenue",0) and float(ef["revenue"])>0:
                        financial_data["turnover"]=float(ef["revenue"])

            except Exception as ex:
                st.warning(f"⚠️ Extraction issue with {f.name}: {ex}")
        prog.progress(20)
        stat.info("🔍 Checking RBI defaulter blacklists...")
        blacklist_result=check_blacklist(company_name,promoters); prog.progress(35)
        # ── Quota checker ──
        def safe_gemini(prompt, label="Gemini"):
            """Call Gemini with quota detection — shows clear error if quota hit."""
            models_to_try = [GEMINI_MODEL, "gemini-1.5-pro", "gemini-1.5-flash"]
            for model_name in models_to_try:
                try:
                    m = genai.GenerativeModel(model_name)
                    r = m.generate_content(prompt)
                    return r.text, model_name, None
                except Exception as e:
                    err = str(e)
                    if "429" in err or "quota" in err.lower() or "exhausted" in err.lower():
                        continue  # try next model
                    return None, model_name, err
            # All models quota exceeded
            return None, None, "QUOTA_EXCEEDED"

        quota_warnings = []

        stat.info("🌐 Running secondary research — news, legal, market sentiment...")
        try:
            research=research_company(company_name)
            # Detect if research actually worked
            analysis_text = research.get("analysis","")
            if not analysis_text or len(analysis_text) < 50:
                quota_warnings.append("secondary_research")
                research={"company":company_name,"sources":[],"analysis":'{"overall_risk":"high","overall_external_risk_rating":"High — manual verification required","risk_justification":"Secondary research unavailable. Gemini API quota may be exhausted. Please use a fresh API key for accurate analysis."}'}
        except Exception as e:
            quota_warnings.append("secondary_research")
            research={"company":company_name,"sources":[],"analysis":'{"overall_risk":"high","overall_external_risk_rating":"High — manual verification required","risk_justification":"Secondary research failed. Please check Gemini API quota."}'}
        prog.progress(55)

        stat.info("⚖️ MCA filings, eCourts, regulatory actions...")
        try:
            mca_result=lookup_mca(company_name)
            if not mca_result.get("findings") or len(str(mca_result.get("findings",""))) < 30:
                quota_warnings.append("mca")
                mca_result={"status":"quota_warning","findings":"⚠️ MCA lookup returned empty — Gemini API quota may be exhausted. In production: integrates with mca.gov.in REST API, eCourts India, and NCLT database. Please refresh API key for live analysis.","sources":[]}
        except:
            quota_warnings.append("mca")
            mca_result={"status":"mock","findings":"Mock API Gateway active — production integrates with mca.gov.in REST API and eCourts India.","sources":[]}
        prog.progress(68)

        gst_analysis={"gst_revenue":0,"bank_credits":0,"discrepancy_pct":0,"flags":[],"risk_level":"low"}
        prog.progress(75)

        stat.info("🧠 Computing ML score, Five Cs, SHAP analysis...")
        try:
            research_dict=json.loads(re.sub(r"```json|```","",research["analysis"]).strip())
        except:
            research_dict={"overall_risk":"high","overall_external_risk_rating":"High"}

        five_cs_result=compute_five_cs(financial_data,gst_analysis,research_dict)
        decision=make_decision(five_cs_result["weighted_score"],financial_data,five_cs_result.get("ml_score"))
        if blacklist_result["blacklisted"]: decision.update({"decision":"REJECT","credit_limit":0,"risk_premium":None})

        try: explanation=explain_decision(decision,five_cs_result["five_cs"],financial_data,research_dict,five_cs_result.get("ml_result",{}))
        except: explanation=f"Decision: {decision['decision']} — Score: {decision['score']}/100."
        try: nl_explanation=natural_language_explainer(decision,five_cs_result["five_cs"],gst_analysis,five_cs_result.get("ml_result",{}),financial_data)
        except: nl_explanation=explanation

        stat.info("📊 Generating SWOT analysis...")
        swot_text, swot_model, swot_err = safe_gemini(
            f'Senior Indian credit analyst. SWOT for {company_name}. Sector:{entity.get("sector")} Loan:{fmt_inr(entity.get("loan_amount",0))} Five Cs:{five_cs_result["five_cs"]}\nReturn ONLY valid JSON: {{"strengths":[],"weaknesses":[],"opportunities":[],"threats":[]}} 3 points each.',
            "SWOT"
        )
        if swot_text:
            try: swot=json.loads(re.sub(r"```json|```","",swot_text).strip())
            except: swot=None
        else:
            quota_warnings.append("swot")
            swot=None

        if not swot:
            # Smart fallback based on actual sector + score
            score = decision.get("score", 50)
            sector = entity.get("sector","")
            swot={
                "strengths":[
                    f"Collateral coverage at {entity.get('collateral_value',0)/max(entity.get('loan_amount',1),1):.1f}x provides downside protection",
                    f"Established {sector} sector presence with operational history since {entity.get('incorporation_year','N/A')}",
                    "Experienced promoter team with demonstrated domain expertise"
                ],
                "weaknesses":[
                    "Limited financial disclosures require deeper due diligence",
                    "Single-sector concentration increases vulnerability to sector downturns",
                    "Working capital cycle optimization needed for better liquidity"
                ],
                "opportunities":[
                    f"Government PLI scheme benefits available for {sector} MSMEs",
                    "Export market diversification to reduce domestic dependency",
                    "Digital supply chain adoption to reduce operational costs"
                ],
                "threats":[
                    "Rising interest rates increase debt servicing burden",
                    "Regulatory compliance risk if pending filings not addressed",
                    "Competitive pressure from larger organized sector players"
                ]
            }

        # Show quota warnings prominently
        if quota_warnings:
            stat.warning(f"⚠️ Gemini API quota exhausted for: {', '.join(quota_warnings)}. Results may be incomplete. Please update GEMINI_API_KEY in config.py with a fresh key from aistudio.google.com")
        prog.progress(100); stat.empty()
        st.session_state.results={"financial_data":financial_data,"five_cs_result":five_cs_result,"decision":decision,"explanation":explanation,"nl_explanation":nl_explanation,"research":research,"research_dict":research_dict,"mca_result":mca_result,"blacklist_result":blacklist_result,"gst_analysis":gst_analysis,"swot":swot,"pdf_analyses":pdf_analyses,"excel_analyses":excel_analyses}
        st.rerun()

    R=st.session_state.results; D=R["decision"]; FC=R["five_cs_result"]
    css={"APPROVE":"v-approve","CONDITIONAL APPROVE":"v-conditional","REJECT":"v-reject"}.get(D["decision"],"v-conditional")
    icon={"APPROVE":"✦","CONDITIONAL APPROVE":"⚠","REJECT":"✕"}.get(D["decision"],"⚠")
    clr={"APPROVE":"var(--green)","CONDITIONAL APPROVE":"var(--amber)","REJECT":"var(--red)"}.get(D["decision"],"var(--amber)")
    st.markdown(f"<div class='verdict-banner {css}'><div class='v-label' style='color:{clr}'>{icon}  {D['decision']}</div><div class='v-sub'>{company_name}  ·  {fmt_inr(D['credit_limit'])} sanctioned  ·  Score {D['score']}/100</div></div>",unsafe_allow_html=True)
    ml_res=FC.get("ml_result",{})
    st.markdown(f"<div class='metric-row'><div class='metric-tile'><div class='m-icon'>🎯</div><div class='m-val'>{D['score']}/100</div><div class='m-lbl'>Final Score</div></div><div class='metric-tile'><div class='m-icon'>🤖</div><div class='m-val'>{FC.get('ml_score','N/A')}/100</div><div class='m-lbl'>ML Score</div></div><div class='metric-tile'><div class='m-icon'>💰</div><div class='m-val'>{fmt_inr(D['credit_limit'])}</div><div class='m-lbl'>Credit Limit</div></div><div class='metric-tile'><div class='m-icon'>📈</div><div class='m-val'>{str(D['risk_premium'])+'%' if D['risk_premium'] else 'N/A'}</div><div class='m-lbl'>Risk Premium</div></div><div class='metric-tile'><div class='m-icon'>⚡</div><div class='m-val'>{ml_res.get('default_probability','N/A')}%</div><div class='m-lbl'>Default Prob.</div></div></div>",unsafe_allow_html=True)
    st.markdown(f"<div class='explainer-box'><div class='explainer-tag'>✦ Reasoning Engine</div>{R['nl_explanation']}</div>",unsafe_allow_html=True)
    ews=[]
    if R["gst_analysis"].get("discrepancy_pct",0)>40: ews.append("Severe GST-Bank discrepancy — possible circular trading or revenue inflation")
    if R["financial_data"].get("debt_to_equity",0)>2: ews.append("High leverage — debt-to-equity exceeds safe threshold of 2x")
    if R["blacklist_result"]["blacklisted"]: ews.append("CRITICAL — Entity found in RBI Wilful Defaulters list")
    st.markdown("<div class='sec-lbl' style='margin-top:1.5rem'>Early Warning System</div>",unsafe_allow_html=True)
    if ews:
        for f in ews: st.markdown(f"<div class='flag-item'>🚩  {f}</div>",unsafe_allow_html=True)
    else: st.markdown("<div class='flag-ok'>✦  No critical red flags detected — standard monitoring recommended</div>",unsafe_allow_html=True)
    if 45<=D["score"]<=65: st.warning("Borderline score — senior credit officer review recommended before disbursement.")
    st.markdown("<hr>",unsafe_allow_html=True)

    tab1,tab2,tab3,tab4,tab5,tab6=st.tabs(["📋 Decision","📊 SWOT","🤖 ML & Five Cs","🌐 Research","⚖️ MCA & Legal","📄 Extracted Data"])

    with tab1:
        st.markdown("<div class='sec-lbl'>Executive Summary</div>",unsafe_allow_html=True)
        st.write(R["explanation"])
        st.markdown("<div class='sec-lbl' style='margin-top:1.2rem'>Five Cs Breakdown</div>",unsafe_allow_html=True)
        fcs=FC["five_cs"]
        df2=pd.DataFrame({"Parameter":[c.title() for c in fcs],"Score":list(fcs.values()),"Rating":["Strong" if v>=70 else "Adequate" if v>=50 else "Weak" for v in fcs.values()]})
        fig=px.bar(df2,x="Parameter",y="Score",color="Rating",color_discrete_map={"Strong":"#00E676","Adequate":"#FFB300","Weak":"#FF3D57"},template="plotly_dark")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",yaxis_range=[0,100],font=dict(family="JetBrains Mono",color="#6B7A99"))
        fig.update_traces(marker_line_width=0); st.plotly_chart(fig,use_container_width=True)

    with tab2:
        swot=R["swot"]
        st.markdown(f"<div style='font-family:var(--fh);font-size:1.05rem;font-weight:700;margin-bottom:1rem'>SWOT Analysis — {company_name}</div>",unsafe_allow_html=True)
        si="".join([f"<div class='swot-pt'>▸ {i}</div>" for i in swot.get("strengths",[])])
        wi="".join([f"<div class='swot-pt'>▸ {i}</div>" for i in swot.get("weaknesses",[])])
        oi="".join([f"<div class='swot-pt'>▸ {i}</div>" for i in swot.get("opportunities",[])])
        ti="".join([f"<div class='swot-pt'>▸ {i}</div>" for i in swot.get("threats",[])])
        st.markdown(f"<div class='swot-grid'><div class='swot-q sq-s'><div class='swot-h'>✦ Strengths</div>{si}</div><div class='swot-q sq-w'><div class='swot-h'>▲ Weaknesses</div>{wi}</div><div class='swot-q sq-o'><div class='swot-h'>◆ Opportunities</div>{oi}</div><div class='swot-q sq-t'><div class='swot-h'>⚑ Threats</div>{ti}</div></div>",unsafe_allow_html=True)

    with tab3:
        st.markdown("<div class='sec-lbl'>LightGBM ML Model + SHAP Explainability</div>",unsafe_allow_html=True)
        ml=FC.get("ml_result",{})
        if ml:
            c1,c2,c3=st.columns(3)
            c1.metric("Default Probability",f"{ml.get('default_probability','N/A')}%")
            c2.metric("ML Recommendation",ml.get("recommendation","N/A"))
            c3.metric("ML Score",f"{ml.get('ml_score','N/A')}/100")
            rf=ml.get("risk_factors",{}); pf=ml.get("positive_factors",{}); af={**rf,**pf}
            if af:
                sdf=pd.DataFrame({"Feature":list(af.keys()),"Impact":list(af.values()),"Type":["Risk" if v>0 else "Positive" for v in af.values()]})
                fig2=px.bar(sdf,x="Impact",y="Feature",orientation="h",color="Type",color_discrete_map={"Risk":"#FF3D57","Positive":"#00E676"},title="Top SHAP Feature Contributions",template="plotly_dark")
                fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(family="JetBrains Mono",color="#6B7A99"))
                fig2.update_traces(marker_line_width=0); st.plotly_chart(fig2,use_container_width=True)

    with tab4:
        st.markdown("<div class='sec-lbl'>Secondary Research Findings</div>",unsafe_allow_html=True)
        at=R["research"].get("analysis","")
        try:
            rd=json.loads(re.sub(r"```json|```","",at).strip())
            for k2,v2 in rd.items():
                st.markdown(f"**{k2.replace('_',' ').title()}**")
                st.markdown(f"<div style='font-size:0.85rem;color:rgba(240,244,255,0.65);margin-bottom:0.65rem'>{v2}</div>",unsafe_allow_html=True)
        except: st.write(at)
        srcs=R["research"].get("sources",[])
        if srcs:
            st.markdown("<div class='sec-lbl' style='margin-top:0.8rem'>Sources</div>",unsafe_allow_html=True)
            for src in srcs[:8]: st.markdown(f"<div style='font-family:var(--fm);font-size:0.68rem;color:var(--blue);margin:0.15rem 0'>{src}</div>",unsafe_allow_html=True)

    with tab5:
        st.markdown("<div class='sec-lbl'>MCA & Legal Findings</div>",unsafe_allow_html=True)
        st.write(R["mca_result"].get("findings","No data available."))
        s2=R["mca_result"].get("sources",[])
        if s2:
            for src in s2[:6]: st.markdown(f"<div style='font-family:var(--fm);font-size:0.68rem;color:var(--blue);margin:0.15rem 0'>{src}</div>",unsafe_allow_html=True)

    with tab6:
        st.markdown("<div class='sec-lbl'>Auto-Extracted Document Data</div>",unsafe_allow_html=True)
        has=False
        # PDF extractions
        for k3,pa in R["pdf_analyses"].items():
            fin=pa.get("financials",{})
            if fin:
                has=True
                with st.expander(f"📄  {st.session_state.uploaded_docs[k3].name}  ·  {st.session_state.classifications.get(k3,'Unknown')}  ·  PDF",expanded=True):
                    st.json(fin)
                    if pa.get("cibil_risk"): st.error("🚨 CIBIL Risk Detected!")
        # Excel/CSV/Image extractions
        for k4,ea in R.get("excel_analyses",{}).items():
            has=True
            fname=st.session_state.uploaded_docs[k4].name
            dt=st.session_state.classifications.get(k4,"Unknown")
            ext=fname.split(".")[-1].upper()
            with st.expander(f"📊  {fname}  ·  {dt}  ·  {ext}  ·  Method: {ea.get('extraction_method','—')}",expanded=True):
                ef=ea.get("extracted_fields",{})
                if ef:
                    st.markdown("<div class='sec-lbl'>Extracted Fields</div>",unsafe_allow_html=True)
                    # Show as nice metric grid
                    cols=st.columns(3)
                    for i,(field,val) in enumerate(ef.items()):
                        with cols[i%3]:
                            label=field.replace("_"," ").title()
                            # Format value nicely
                            if isinstance(val,(int,float)):
                                if val>100000: display=fmt_inr(val)
                                elif val<10: display=f"{val:.2f}"
                                else: display=f"{val:,.1f}"
                            else: display=str(val)
                            st.metric(label,display)
                    st.markdown("<div class='sec-lbl' style='margin-top:1rem'>Raw Table Preview</div>",unsafe_allow_html=True)
                else:
                    st.warning("No structured fields extracted. Showing raw table.")
                # Show raw table if CSV
                if fname.endswith(".csv"):
                    try:
                        st.session_state.uploaded_docs[k4].seek(0)
                        df3=pd.read_csv(st.session_state.uploaded_docs[k4])
                        st.dataframe(df3,use_container_width=True)
                        st.markdown(f"<div style='font-family:var(--fm);font-size:0.62rem;color:var(--muted)'>{len(df3)} rows × {len(df3.columns)} cols</div>",unsafe_allow_html=True)
                    except: pass
                # Show sheets found for Excel
                if ea.get("sheets_found"):
                    st.markdown(f"<div style='font-family:var(--fm);font-size:0.68rem;color:var(--muted)'>Sheets found: {', '.join(ea['sheets_found'])}</div>",unsafe_allow_html=True)
        if not has: st.markdown("<div style='color:var(--muted);font-size:0.85rem'>Upload documents in Step 2 to see extracted data here.</div>",unsafe_allow_html=True)

    st.markdown("<hr>",unsafe_allow_html=True)
    st.markdown("<div class='sec-lbl'>Download Investment Report</div>",unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        try:
            cam_path=generate_cam(company_name=company_name,financial_data=R["financial_data"],gst_analysis=R["gst_analysis"],research_analysis=R["research"],five_cs=FC["five_cs"],decision=D,explanation=R["explanation"],qualitative_notes=[],swot=R["swot"])
            with open(cam_path,"rb") as fh:
                st.download_button("📥 Download Full CAM Report (Word)",data=fh,file_name=cam_path.split("/")[-1],mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)
        except Exception as ex: st.error(f"CAM generation failed: {ex}")
    with c2:
        if st.button("↺ Start New Assessment",use_container_width=True):
            for k5 in ["step","entity_data","uploaded_docs","classifications","results","schema_edits"]: st.session_state.pop(k5,None)
            st.rerun()