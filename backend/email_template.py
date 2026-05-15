# email_template.py
from typing import Any
import os, json
import pandas as pd
from google import genai
from google.genai import types
from config import gemini_enabled, GEMINI_MODEL

def generate_email_template(invoice_row: pd.Series, final_action: str) -> dict[str, str]:
    if final_action in ["no_email_needed", "not_eligible"]:
        return {"email_subject": "", "email_body": ""}

    if not gemini_enabled():
        return _fallback_template(invoice_row)

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = f"""
You are an accounts receivable assistant. Write a professional payment reminder email.

Invoice details:
- Customer: {invoice_row.get('customer_name')}
- Invoice: {invoice_row.get('document_number')}
- Amount: ${invoice_row.get('invoice_amount')}
- Due Date: {invoice_row.get('due_date')}
- Aging Days: {invoice_row.get('aging_days')}
- Reminder Stage: {invoice_row.get('reminder_stage_label')}
- Action: {final_action}

Rules:
- Tone should escalate with reminder stage (polite → firm → urgent)
- Keep it concise and professional
- Sign off as "Accounts Receivable Team"
- Return ONLY valid JSON, no markdown
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "email_subject": {"type": "string"},
                    "email_body": {"type": "string"}
                },
                "required": ["email_subject", "email_body"]
            }
        )
    )

    return json.loads(response.text)


def _fallback_template(invoice_row: pd.Series) -> dict[str, str]:
    doc = invoice_row.get('document_number', '')
    return {
        "email_subject": f"Payment Reminder: Invoice {doc}",
        "email_body": f"Dear {invoice_row.get('customer_name')},\n\nThis is a reminder for invoice {doc}.\n\nBest regards,\nAccounts Receivable Team"
    }