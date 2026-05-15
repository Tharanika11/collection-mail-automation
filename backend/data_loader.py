import json
from pathlib import Path
from typing import Any

import pandas as pd


def load_ar_excel(file_path: Path) -> pd.DataFrame:
    """
    Loads the AR Excel dataset.
    Expected file: data/synthetic_customer_ar_data.xlsx
    """

    if not file_path.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    df = pd.read_excel(file_path, engine="openpyxl")

    # Clean column names
    df.columns = [str(col).strip() for col in df.columns]

    return df


def load_customer_replies(file_path: Path) -> list[dict[str, Any]]:
    """
    Loads sample customer email replies from JSON.
    This simulates checking customer replies without Gmail.
    """

    if not file_path.exists():
        return []

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    raise ValueError("customer_replies.json must contain a JSON array.")