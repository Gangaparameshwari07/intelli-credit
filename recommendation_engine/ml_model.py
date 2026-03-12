import pandas as pd
import numpy as np
import lightgbm as lgb
import shap
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

MODEL_PATH = "data/sample/lightgbm_model.pkl"

FEATURES = [
    "Loan Amount", "Interest Rate", "Debit to Income",
    "Revolving Balance", "Revolving Utilities", "Total Current Balance",
    "Total Revolving Credit Limit", "Delinquency - two years",
    "Inquires - six months", "Open Account", "Public Record", "Total Accounts"
]


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df[FEATURES + ["Loan Status"]].copy()
    df.dropna(inplace=True)
    return df


def train_model():
    df = pd.read_csv("data/sample/train.csv")
    df = preprocess(df)
    X = df[FEATURES]
    y = df["Loan Status"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    model = lgb.LGBMClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        random_state=42,
        verbose=-1,
        class_weight="balanced"
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"Model saved to {MODEL_PATH}")
    return model


def load_model():
    if not os.path.exists(MODEL_PATH):
        print("Model not found. Training now...")
        return train_model()
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def predict_default(financial_data: dict) -> dict:
    model = load_model()
    input_df = pd.DataFrame([{
        "Loan Amount": financial_data.get("loan_amount_requested", 0),
        "Interest Rate": financial_data.get("interest_rate", 10.0),
        "Debit to Income": financial_data.get("debt_to_income", 20.0),
        "Revolving Balance": financial_data.get("revolving_balance", 0),
        "Revolving Utilities": financial_data.get("revolving_utilities", 50.0),
        "Total Current Balance": financial_data.get("total_current_balance", 0),
        "Total Revolving Credit Limit": financial_data.get("total_revolving_credit_limit", 0),
        "Delinquency - two years": financial_data.get("delinquency_two_years", 0),
        "Inquires - six months": financial_data.get("inquiries_six_months", 0),
        "Open Account": financial_data.get("open_accounts", 5),
        "Public Record": financial_data.get("public_record", 0),
        "Total Accounts": financial_data.get("total_accounts", 10),
    }])
    prob = model.predict_proba(input_df)[0]
    default_prob = round(prob[1] * 100, 2)
    ml_score = round((1 - prob[1]) * 100, 2)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(input_df)
    if isinstance(shap_values, list):
        sv = shap_values[1][0]
    else:
        sv = shap_values[0]
    feature_impact = {}
    for i, feat in enumerate(FEATURES):
        feature_impact[feat] = round(float(sv[i]), 4)
    top_risks = dict(sorted(feature_impact.items(), key=lambda x: x[1], reverse=True)[:3])
    top_positives = dict(sorted(feature_impact.items(), key=lambda x: x[1])[:3])
    return {
        "ml_score": ml_score,
        "default_probability": default_prob,
        "risk_factors": top_risks,
        "positive_factors": top_positives,
        "recommendation": "HIGH RISK" if default_prob > 50 else "MEDIUM RISK" if default_prob > 25 else "LOW RISK"
    }