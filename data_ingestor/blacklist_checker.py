import pandas as pd
import os

DEFAULTER_FILES = [
    "data/sample/defaulters_pnb.csv",
    "data/sample/defaulters_idbi.csv",
    "data/sample/defaulters_bob.csv",
    "data/sample/defaulters_syndicate.csv",
]

def load_defaulters() -> pd.DataFrame:
    dfs = []
    for f in DEFAULTER_FILES:
        if os.path.exists(f):
            try:
                df = pd.read_csv(f, on_bad_lines='skip')
                dfs.append(df)
            except:
                continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def check_blacklist(company_name: str, promoter_names: list = []) -> dict:
    df = load_defaulters()
    if df.empty:
        return {"blacklisted": False, "matches": [], "risk": "unknown"}

    search_terms = [company_name.lower()] + [p.lower() for p in promoter_names]
    matches = []

    for col in ["party", "PRTY"]:
        if col in df.columns:
            for term in search_terms:
                hits = df[df[col].str.lower().str.contains(term, na=False)]
                if not hits.empty:
                    for _, row in hits.iterrows():
                        matches.append({
                            "name": row.get(col, ""),
                            "bank": row.get("bknm", row.get("BKNM", "")),
                            "outstanding_amount": row.get("osamt", row.get("OSAMT (Rs. Lac)", "")),
                            "suit_filed": row.get("suit", row.get("SUIT", ""))
                        })

    return {
        "blacklisted": len(matches) > 0,
        "matches": matches,
        "risk": "critical" if len(matches) > 0 else "clear"
    }