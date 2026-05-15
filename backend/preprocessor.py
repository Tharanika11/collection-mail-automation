# from typing import Any

# import pandas as pd


# REQUIRED_COLUMNS = [
#     "Document Number",
#     "Customer Name",
#     "Customer Email",
#     "Invoice Amount",
#     "Issue Date",
#     "Due Date",
#     "Aging Days",
# ]


# def validate_required_columns(df: pd.DataFrame) -> None:
#     """
#     Checks whether the Excel file contains required columns.
#     """

#     missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]

#     if missing_columns:
#         raise ValueError(
#             "Missing required columns: " + ", ".join(missing_columns)
#         )


# def safe_string(value: Any) -> str:
#     """
#     Converts a value to a clean string.
#     """

#     if pd.isna(value):
#         return ""

#     return str(value).strip()


# def safe_float(value: Any, default: float = 0.0) -> float:
#     """
#     Converts a value to float safely.
#     """

#     try:
#         if pd.isna(value):
#             return default

#         return float(value)

#     except (ValueError, TypeError):
#         return default


# def format_date(value: Any) -> str:
#     """
#     Formats Excel/Pandas date values safely.
#     """

#     if pd.isna(value):
#         return "N/A"

#     try:
#         date_value = pd.to_datetime(value)
#         return date_value.strftime("%Y-%m-%d")

#     except Exception:
#         return str(value)


# def preprocess_invoices(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
#     """
#     Cleans and validates invoice records.

#     Valid invoice rules:
#     - Document Number must start with INV-
#     - Aging Days must be greater than 0
#     - Customer Email must contain @
#     - Duplicate Document Numbers are skipped
#     """

#     validate_required_columns(df)

#     seen_documents = set()
#     valid_records = []
#     skipped_records = []

#     for index, row in df.iterrows():
#         row_number = index + 2

#         document_number = safe_string(row.get("Document Number"))
#         customer_name = safe_string(row.get("Customer Name")) or "Unknown"
#         customer_email = safe_string(row.get("Customer Email"))
#         invoice_amount = safe_float(row.get("Invoice Amount"))
#         issue_date = format_date(row.get("Issue Date"))
#         due_date = format_date(row.get("Due Date"))
#         aging_days = safe_float(row.get("Aging Days"))
#         aging_bucket = safe_string(row.get("Aging Bucket"))

#         if not document_number:
#             skipped_records.append({
#                 "row_number": row_number,
#                 "document_number": document_number,
#                 "reason": "Missing document number"
#             })
#             continue

#         if not document_number.startswith("INV-"):
#             skipped_records.append({
#                 "row_number": row_number,
#                 "document_number": document_number,
#                 "reason": "Document number is not an invoice"
#             })
#             continue

#         if aging_days <= 0:
#             skipped_records.append({
#                 "row_number": row_number,
#                 "document_number": document_number,
#                 "reason": "Aging days is zero or invalid"
#             })
#             continue

#         if document_number in seen_documents:
#             skipped_records.append({
#                 "row_number": row_number,
#                 "document_number": document_number,
#                 "reason": "Duplicate document number"
#             })
#             continue

#         if not customer_email or "@" not in customer_email:
#             skipped_records.append({
#                 "row_number": row_number,
#                 "document_number": document_number,
#                 "reason": "Missing or invalid customer email"
#             })
#             continue

#         seen_documents.add(document_number)

#         valid_records.append({
#             "document_number": document_number,
#             "customer_name": customer_name,
#             "customer_email": customer_email,
#             "invoice_amount": invoice_amount,
#             "issue_date": issue_date,
#             "due_date": due_date,
#             "aging_days": int(aging_days),
#             "aging_bucket": aging_bucket
#         })

#     valid_df = pd.DataFrame(valid_records)
#     skipped_df = pd.DataFrame(skipped_records)

#     return valid_df, skipped_df

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


def validate_required_columns(df: pd.DataFrame) -> None:
    """
    Checks whether the Excel file contains required columns.
    """

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]

    if missing_columns:
        raise ValueError(
            "Missing required columns: " + ", ".join(missing_columns)
        )


def safe_string(value: Any) -> str:
    """
    Converts a value to a clean string.
    """

    if pd.isna(value):
        return ""

    return str(value).strip()


def safe_float(value: Any, default: float | None = None) -> float | None:
    """
    Converts a value to float safely.

    Important:
    We return None by default instead of 0 so that missing Excel formula values
    are not treated as real aging days.
    """

    try:
        if pd.isna(value):
            return default

        return float(value)

    except (ValueError, TypeError):
        return default


def safe_date(value: Any) -> pd.Timestamp | None:
    """
    Converts Excel/Pandas date values into a Timestamp safely.
    """

    if pd.isna(value):
        return None

    try:
        parsed_date = pd.to_datetime(value, errors="coerce")

        if pd.isna(parsed_date):
            return None

        return parsed_date.normalize()

    except Exception:
        return None


def format_date(value: Any) -> str:
    """
    Formats Excel/Pandas date values safely.
    """

    parsed_date = safe_date(value)

    if parsed_date is None:
        return "N/A"

    return parsed_date.strftime("%Y-%m-%d")


def calculate_aging_days(
    excel_aging_value: Any,
    due_date_value: Any,
    as_of_date: date | None = None
) -> int:
    """
    Calculates aging days safely.

    Priority:
    1. Use Aging Days from Excel if it is valid and greater than 0.
    2. If Aging Days is missing, zero, or invalid, recompute from Due Date.
    3. If both are invalid, return 0.

    This avoids issues where Excel formula values are not cached.
    """

    excel_aging = safe_float(excel_aging_value, default=None)

    if excel_aging is not None and excel_aging > 0:
        return int(excel_aging)

    due_date = safe_date(due_date_value)

    if due_date is None:
        return 0

    if as_of_date is None:
        process_date = pd.Timestamp.today().normalize()
    else:
        process_date = pd.Timestamp(as_of_date).normalize()

    aging_days = (process_date - due_date).days

    if aging_days <= 0:
        return 0

    return int(aging_days)


def preprocess_invoices(
    df: pd.DataFrame,
    as_of_date: date | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Cleans and validates invoice records.

    Valid invoice rules:
    - Document Number must start with INV-
    - Aging Days must be greater than 0
    - Customer Email must contain @
    - Duplicate Document Numbers are skipped

    Aging Days handling:
    - Uses Excel Aging Days if valid.
    - Falls back to recomputing aging from Due Date if Excel formula value is missing or zero.
    """

    validate_required_columns(df)

    seen_documents = set()
    valid_records = []
    skipped_records = []

    for index, row in df.iterrows():
        row_number = index + 2

        document_number = safe_string(row.get("Document Number"))
        customer_name = safe_string(row.get("Customer Name")) or "Unknown"
        customer_email = safe_string(row.get("Customer Email"))
        invoice_amount = safe_float(row.get("Invoice Amount"), default=0.0)
        issue_date = format_date(row.get("Issue Date"))
        due_date = format_date(row.get("Due Date"))

        aging_days = calculate_aging_days(
            excel_aging_value=row.get("Aging Days"),
            due_date_value=row.get("Due Date"),
            as_of_date=as_of_date
        )

        aging_bucket = safe_string(row.get("Aging Bucket"))

        if not document_number:
            skipped_records.append({
                "row_number": row_number,
                "document_number": document_number,
                "reason": "Missing document number"
            })
            continue

        if not document_number.startswith("INV-"):
            skipped_records.append({
                "row_number": row_number,
                "document_number": document_number,
                "reason": "Document number is not an invoice"
            })
            continue

        if aging_days <= 0:
            skipped_records.append({
                "row_number": row_number,
                "document_number": document_number,
                "reason": "Aging days is zero or invoice is not overdue"
            })
            continue

        if document_number in seen_documents:
            skipped_records.append({
                "row_number": row_number,
                "document_number": document_number,
                "reason": "Duplicate document number"
            })
            continue

        if not customer_email or "@" not in customer_email:
            skipped_records.append({
                "row_number": row_number,
                "document_number": document_number,
                "reason": "Missing or invalid customer email"
            })
            continue

        seen_documents.add(document_number)

        valid_records.append({
            "document_number": document_number,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "invoice_amount": invoice_amount,
            "issue_date": issue_date,
            "due_date": due_date,
            "aging_days": aging_days,
            "aging_bucket": aging_bucket
        })

    valid_df = pd.DataFrame(valid_records)
    skipped_df = pd.DataFrame(skipped_records)

    return valid_df, skipped_df