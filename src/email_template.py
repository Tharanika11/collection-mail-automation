from typing import Any

import pandas as pd


def format_currency(amount: Any) -> str:
    """
    Formats invoice amount as USD currency.
    """

    try:
        return "${:,.2f}".format(float(amount))
    except (ValueError, TypeError):
        return "N/A"


def generate_email_template(
    invoice_row: pd.Series,
    final_action: str
) -> dict[str, str]:
    """
    Generates a reminder email based on reminder stage.
    """

    customer_name = invoice_row.get("customer_name", "Customer")
    document_number = invoice_row.get("document_number", "")
    amount = format_currency(invoice_row.get("invoice_amount"))
    due_date = invoice_row.get("due_date", "N/A")
    aging_days = invoice_row.get("aging_days", "N/A")
    stage = invoice_row.get("reminder_stage")

    if final_action in ["no_email_needed", "not_eligible"]:
        return {
            "email_subject": "",
            "email_body": ""
        }

    if stage == "initial":
        subject = f"Payment Reminder: Invoice {document_number}"
        body = f"""Dear {customer_name},

I hope you are doing well.

This is a kind reminder that invoice {document_number}, amounting to {amount}, was due on {due_date}.

Please arrange the payment at your earliest convenience. If payment has already been made, kindly ignore this message.

Thank you.

Best regards,
Accounts Receivable Team"""

    elif stage == "first":
        subject = f"First Reminder: Outstanding Invoice {document_number}"
        body = f"""Dear {customer_name},

This is a first reminder regarding the outstanding invoice {document_number}.

Invoice Amount: {amount}
Due Date: {due_date}
Aging Days: {aging_days}

Please arrange the payment soon or let us know if there are any issues related to this invoice.

Best regards,
Accounts Receivable Team"""

    elif stage == "second":
        subject = f"Second Reminder: Invoice {document_number} Still Outstanding"
        body = f"""Dear {customer_name},

Our records show that invoice {document_number} is still unpaid.

Amount Due: {amount}
Due Date: {due_date}
Aging Days: {aging_days}

Please make the payment as soon as possible or contact us if you need any clarification.

Best regards,
Accounts Receivable Team"""

    elif stage == "third":
        subject = f"Third Reminder: Urgent Payment Required for Invoice {document_number}"
        body = f"""Dear {customer_name},

This is the third reminder for the overdue invoice {document_number}.

Amount Due: {amount}
Due Date: {due_date}
Aging Days: {aging_days}

Please settle this payment immediately to avoid further escalation.

Best regards,
Accounts Receivable Team"""

    elif stage == "escalation":
        subject = f"Urgent Escalation Notice: Invoice {document_number}"
        body = f"""Dear {customer_name},

This is an urgent notice regarding invoice {document_number}, which remains unpaid for more than 10 days.

Amount Due: {amount}
Due Date: {due_date}

If payment is not received soon, this matter may be escalated to the management or collections team.

Please treat this as urgent.

Best regards,
Accounts Receivable Team"""

    else:
        subject = f"Payment Reminder: Invoice {document_number}"
        body = f"""Dear {customer_name},

This is a reminder regarding invoice {document_number}.

Amount Due: {amount}
Due Date: {due_date}

Please arrange the payment at your earliest convenience.

Best regards,
Accounts Receivable Team"""

    return {
        "email_subject": subject,
        "email_body": body
    }