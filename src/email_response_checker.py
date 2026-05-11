from typing import Any

import pandas as pd


def normalize_text(value: Any) -> str:
    """
    Converts a value into lowercase trimmed text.
    """

    if value is None:
        return ""

    return str(value).strip().lower()


def find_customer_reply(
    invoice_row: pd.Series,
    customer_replies: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """
    Finds a matching customer reply for an invoice.

    Matching logic:
    - Match by document number, OR
    - Match by customer email
    """

    invoice_number = normalize_text(invoice_row.get("document_number"))
    customer_email = normalize_text(invoice_row.get("customer_email"))

    matched_replies = []

    for reply in customer_replies:
        reply_invoice_number = normalize_text(
            reply.get("document_number") or reply.get("invoice_number")
        )
        reply_customer_email = normalize_text(reply.get("customer_email"))
        reply_text = normalize_text(reply.get("reply"))

        invoice_matches = (
            reply_invoice_number == invoice_number
            or invoice_number in reply_text
        )

        email_matches = reply_customer_email == customer_email

        if invoice_matches or email_matches:
            matched_replies.append(reply)

    if not matched_replies:
        return None

    # Return latest reply if received_date exists
    matched_replies.sort(
        key=lambda item: item.get("received_date", ""),
        reverse=True
    )

    return matched_replies[0]


def build_reply_check_results(
    invoices_df: pd.DataFrame,
    customer_replies: list[dict[str, Any]]
) -> pd.DataFrame:
    """
    Creates a dataframe showing whether each invoice has a customer reply.
    """

    results = []

    for _, invoice in invoices_df.iterrows():
        reply = find_customer_reply(invoice, customer_replies)

        results.append({
            "document_number": invoice.get("document_number"),
            "customer_name": invoice.get("customer_name"),
            "customer_email": invoice.get("customer_email"),
            "has_reply": reply is not None,
            "reply_received_date": reply.get("received_date") if reply else "",
            "reply_text": reply.get("reply") if reply else ""
        })

    return pd.DataFrame(results)