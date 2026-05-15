# decision_engine.py
from typing import Any
import os, json
import pandas as pd
from google import genai
from google.genai import types
from config import gemini_enabled, GEMINI_MODEL

ALLOWED_ACTIONS = ["send_reminder", "needs_human_review", "escalate", "no_email_needed", "not_eligible"]

def decide_final_action(invoice_row: pd.Series, classification_result: dict[str, Any]) -> dict[str, Any]:
    if not gemini_enabled():
        return _fallback_decision(invoice_row, classification_result)

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = f"""
You are a collections workflow decision engine.

Given an invoice and its reply classification, decide the correct action.

Invoice:
- Reminder Stage: {invoice_row.get('reminder_stage')}
- Aging Days: {invoice_row.get('aging_days')}

Classification:
- Result: {classification_result.get('classification')}
- Summary: {classification_result.get('summary')}
- Human Review Required: {classification_result.get('human_review_required')}
- Review Reason: {classification_result.get('review_reason')}

Action rules:
- "not_eligible": no reminder stage assigned
- "no_email_needed": payment confirmed, no further action
- "needs_human_review": dispute, copy_request, payment_promised, ooo_bounce, payment_made, or any ambiguity
- "escalate": aging > 10 days, no blocking reply
- "send_reminder": eligible invoice, no reply, no flags
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "final_action": {"type": "string", "enum": ALLOWED_ACTIONS},
                    "action_reason": {"type": "string"},
                    "human_review_required": {"type": "boolean"},
                    "should_generate_email": {"type": "boolean"}
                },
                "required": ["final_action", "action_reason", "human_review_required", "should_generate_email"]
            }
        )
    )

    return json.loads(response.text)


def _fallback_decision(invoice_row, classification_result):
    classification = classification_result.get("classification")
    aging_days = int(invoice_row.get("aging_days") or 0)
    reminder_stage = invoice_row.get("reminder_stage")

    if not reminder_stage:
        return {
            "final_action": "not_eligible",
            "action_reason": "No reminder stage is assigned.",
            "human_review_required": False,
            "should_generate_email": False,
        }

    if classification == "no_reply":
        if aging_days > 10:
            return {
                "final_action": "escalate",
                "action_reason": "Invoice aging is greater than 10 days with no blocking reply.",
                "human_review_required": True,
                "should_generate_email": False,
            }

        return {
            "final_action": "send_reminder",
            "action_reason": "Invoice is eligible and no customer reply was found.",
            "human_review_required": False,
            "should_generate_email": True,
        }

    if classification == "payment_made":
        return {
            "final_action": "no_email_needed",
            "action_reason": "Customer says payment has already been made.",
            "human_review_required": True,
            "should_generate_email": False,
        }

    if classification in ["dispute", "copy_request", "payment_promised", "ooo_bounce", "no_meaningful"]:
        return {
            "final_action": "needs_human_review",
            "action_reason": f"Customer reply classified as {classification}.",
            "human_review_required": True,
            "should_generate_email": False,
        }

    return {
        "final_action": "needs_human_review",
        "action_reason": "Unable to determine final action safely.",
        "human_review_required": True,
        "should_generate_email": False,
    }
    # keep your existing if/else logic here as fallback
    ...