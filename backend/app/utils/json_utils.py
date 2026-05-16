from typing import Any

import pandas as pd


def dataframe_to_json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []

    return [
        {key: clean_value(value) for key, value in record.items()}
        for record in df.to_dict(orient="records")
    ]


def clean_value(value: Any) -> Any:
    if pd.isna(value):
        return ""

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value

    return value
