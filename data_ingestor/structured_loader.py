import pandas as pd
import os

def load_csv(filepath: str) -> pd.DataFrame:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    return pd.read_csv(filepath)


def load_financial_data(filepath: str) -> dict:
    df = load_csv(filepath)
    return df.to_dict(orient="records")


def validate_gst_columns(df: pd.DataFrame) -> bool:
    required = ["taxable_value"]
    return all(col in df.columns for col in required)


def validate_bank_columns(df: pd.DataFrame) -> bool:
    required = ["amount", "transaction_type"]
    return all(col in df.columns for col in required)


def load_and_validate(gst_path: str, bank_path: str) -> dict:
    gst_df = load_csv(gst_path)
    bank_df = load_csv(bank_path)

    return {
        "gst_valid": validate_gst_columns(gst_df),
        "bank_valid": validate_bank_columns(bank_df),
        "gst_df": gst_df,
        "bank_df": bank_df
    }