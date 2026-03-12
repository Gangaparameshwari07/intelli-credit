import pandas as pd
import os


def load_from_databricks_or_local(filepath: str) -> pd.DataFrame:
    """
    In production this connects to Databricks.
    For prototype we load from local files.
    Databricks connection can be enabled by setting env vars.
    """
    databricks_host = os.getenv("DATABRICKS_HOST")
    databricks_token = os.getenv("DATABRICKS_TOKEN")
    databricks_path = os.getenv("DATABRICKS_HTTP_PATH")

    if databricks_host and databricks_token and databricks_path:
        try:
            from databricks import sql
            connection = sql.connect(
                server_hostname=databricks_host,
                http_path=databricks_path,
                access_token=databricks_token
            )
            cursor = connection.cursor()
            cursor.execute(f"SELECT * FROM credit_data LIMIT 1000")
            df = cursor.fetchall_arrow().to_pandas()
            connection.close()
            return df
        except Exception as e:
            print(f"Databricks connection failed, falling back to local: {e}")

    return pd.read_csv(filepath)


def get_borrower_history(company_name: str) -> dict:
    """
    Fetches historical borrower data from Databricks or local store.
    """
    databricks_host = os.getenv("DATABRICKS_HOST")
    databricks_token = os.getenv("DATABRICKS_TOKEN")
    databricks_path = os.getenv("DATABRICKS_HTTP_PATH")

    if databricks_host and databricks_token and databricks_path:
        try:
            from databricks import sql
            connection = sql.connect(
                server_hostname=databricks_host,
                http_path=databricks_path,
                access_token=databricks_token
            )
            cursor = connection.cursor()
            cursor.execute(f"SELECT * FROM borrower_history WHERE company_name = '{company_name}'")
            rows = cursor.fetchall()
            connection.close()
            if rows:
                return {"found": True, "history": rows}
        except Exception as e:
            print(f"Databricks lookup failed: {e}")

    return {
        "found": False,
        "message": "No historical data found. Using real-time analysis only.",
        "databricks_ready": bool(databricks_host)
    }