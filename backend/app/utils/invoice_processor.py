from datetime import date
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = [
    "Document Number",
    "Customer Name",
    "Customer Email",
    "Invoice Amount",
    "Issue Date",
    "Due Date",
    "Aging Days",
]

REMINDER_STAGE_LABELS = {
    "initial": "Initial Reminder",
    "first": "1st Reminder",
    "second": "2nd Reminder",
    "third": "3rd Reminder",
    "escalation": "Escalation Email",
}


def preprocess_invoices(
    df: pd.DataFrame,
    as_of_date: date | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Cleans AR records and keeps only valid invoice records.

    Rules:
    - Only Document Number values starting with INV- are treated as invoices.
    - Aging Days <= 0 are ignored because they are not overdue.
    - Duplicates and invalid emails are skipped with reasons.
    - Reminder stage is added for downstream output.
    """

    validate_required_columns(df)

    seen_documents: set[str] = set()
    valid_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        processed = process_invoice_row(
            row=row,
            row_number=index + 2,
            seen_documents=seen_documents,
            as_of_date=as_of_date,
        )

        if processed["is_valid"]:
            record = processed["record"]
            valid_records.append(record)
            seen_documents.add(record["document_number"])
        else:
            skipped_records.append(processed["record"])

    return pd.DataFrame(valid_records), pd.DataFrame(skipped_records)


def process_invoice_row(
    row: pd.Series,
    row_number: int,
    seen_documents: set[str],
    as_of_date: date | None,
) -> dict[str, Any]:
    document_number = safe_string(row.get("Document Number"))
    customer_name = safe_string(row.get("Customer Name")) or "Unknown"
    customer_email = safe_string(row.get("Customer Email"))

    aging_days = calculate_aging_days(
        excel_aging_value=row.get("Aging Days"),
        due_date_value=row.get("Due Date"),
        as_of_date=as_of_date,
    )

    invalid_reason = get_invalid_reason(
        document_number=document_number,
        customer_email=customer_email,
        aging_days=aging_days,
        seen_documents=seen_documents,
    )

    if invalid_reason:
        return {
            "is_valid": False,
            "record": {
                "row_number": row_number,
                "document_number": document_number,
                "reason": invalid_reason,
            },
        }

    reminder_stage = assign_reminder_stage(aging_days)

    return {
        "is_valid": True,
        "record": {
            "document_number": document_number,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "invoice_amount": safe_float(row.get("Invoice Amount"), default=0.0),
            "issue_date": format_date(row.get("Issue Date")),
            "due_date": format_date(row.get("Due Date")),
            "aging_days": aging_days,
            "aging_bucket": safe_string(row.get("Aging Bucket")),
            "reminder_stage": reminder_stage,
            "reminder_stage_label": get_reminder_stage_label(reminder_stage),
            "is_eligible_for_reminder": reminder_stage is not None,
        },
    }


def validate_required_columns(df: pd.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]

    if missing_columns:
        raise ValueError("Missing required columns: " + ", ".join(missing_columns))


def get_invalid_reason(
    document_number: str,
    customer_email: str,
    aging_days: int,
    seen_documents: set[str],
) -> str | None:
    if not document_number:
        return "Missing document number"

    if not document_number.startswith("INV-"):
        return "Document number is not an invoice"

    if aging_days <= 0:
        return "Aging days is zero or invoice is not overdue"

    if document_number in seen_documents:
        return "Duplicate document number"

    if not customer_email or "@" not in customer_email:
        return "Missing or invalid customer email"

    return None


def assign_reminder_stage(aging_days: int) -> str | None:
    if aging_days == 4:
        return "initial"

    if aging_days == 6:
        return "first"

    if aging_days == 8:
        return "second"

    if aging_days == 10:
        return "third"

    if aging_days > 10:
        return "escalation"

    return None


def get_reminder_stage_label(stage: str | None) -> str:
    if stage is None:
        return "Not Eligible"

    return REMINDER_STAGE_LABELS.get(stage, "Not Eligible")


def calculate_aging_days(
    excel_aging_value: Any,
    due_date_value: Any,
    as_of_date: date | None = None,
) -> int:
    excel_aging = safe_float(excel_aging_value, default=None)

    if excel_aging is not None and excel_aging > 0:
        return int(excel_aging)

    due_date = safe_date(due_date_value)

    if due_date is None:
        return 0

    process_date = (
        pd.Timestamp.today().normalize()
        if as_of_date is None
        else pd.Timestamp(as_of_date).normalize()
    )

    return max(int((process_date - due_date).days), 0)


def safe_string(value: Any) -> str:
    if pd.isna(value):
        return ""

    return str(value).strip()


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if pd.isna(value):
            return default

        return float(value)

    except (ValueError, TypeError):
        return default


def safe_date(value: Any) -> pd.Timestamp | None:
    if pd.isna(value):
        return None

    parsed_date = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed_date):
        return None

    return parsed_date.normalize()


def format_date(value: Any) -> str:
    parsed_date = safe_date(value)

    if parsed_date is None:
        return "N/A"

    return parsed_date.strftime("%Y-%m-%d")