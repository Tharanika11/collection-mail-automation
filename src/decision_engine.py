
from typing import Any

import pandas as pd


def decide_final_action(
    invoice_row: pd.Series,
    classification_result: dict[str, Any]
) -> dict[str, Any]:
    """
    Decides the final action for an invoice based on:
    - Reminder stage
    - Reply classification
    - Human review requirement
    """

    reminder_stage = invoice_row.get("reminder_stage")
    classification = classification_result.get("classification")
    human_review_required = classification_result.get("human_review_required", False)

    # 1. Invoice not eligible for any reminder stage
    if not reminder_stage:
        return {
            "final_action": "not_eligible",
            "action_reason": "Invoice is not eligible for reminder based on aging days.",
            "human_review_required": False,
            "should_generate_email": False
        }

    # 2. Customer claims payment already made — suppress email but flag for reconciliation
    # if classification == "payment_made":
    #     return {
    #         "final_action": "no_email_needed",
    #         "action_reason": "Customer says payment has already been made. Reconciliation required.",
    #         "human_review_required": True,
    #         "should_generate_email": False
    #     }
    if classification == "payment_made":
        return {
           "final_action": "needs_human_review",
           "action_reason": "Customer says payment has already been made. Reconciliation required before closing the reminder flow.",
           "human_review_required": True,
           "should_generate_email": False
    }

    # 3. Bounced / OOO / undeliverable — human must fix contact details, no point drafting
    if classification == "ooo_bounce":
        return {
            "final_action": "needs_human_review",
            "action_reason": "Email undeliverable or out-of-office — contact details need verification.",
            "human_review_required": True,
            "should_generate_email": False
        }

    # 4. Classifications that always require human review before any email is sent/drafted
    if classification in ["payment_promised", "dispute", "copy_request", "no_meaningful"]:
        return {
            "final_action": "needs_human_review",
            "action_reason": classification_result.get("review_reason", "Manual review required."),
            "human_review_required": True,
            "should_generate_email": True
        }

    # 5. Classifier flagged human review for any other reason (e.g. low confidence, partial payment)
    #    Must be checked BEFORE escalation so it isn't silently overridden
    if human_review_required:
        return {
            "final_action": "needs_human_review",
            "action_reason": classification_result.get("review_reason", "Manual review required."),
            "human_review_required": True,
            "should_generate_email": True
        }

    # 6. Escalation — only reached when no blocking reply and no human review flag
    if reminder_stage == "escalation":
        return {
            "final_action": "escalate",
            "action_reason": "Invoice is overdue for more than 10 days and no blocking reply was found.",
            "human_review_required": False,
            "should_generate_email": True
        }

    # 7. Unknown / future classification values — fail safe to human review
    if classification and classification not in ["no_reply", None]:
        return {
            "final_action": "needs_human_review",
            "action_reason": f"Unrecognized classification '{classification}' — routing to human review as a precaution.",
            "human_review_required": True,
            "should_generate_email": False
        }

    # 8. Default — no reply, eligible invoice, no flags raised → send reminder
    return {
        "final_action": "send_reminder",
        "action_reason": "Invoice is eligible and no blocking customer reply was found.",
        "human_review_required": False,
        "should_generate_email": True
    }