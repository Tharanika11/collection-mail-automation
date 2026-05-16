import logging
from typing import Any

import pandas as pd
from fastapi.encoders import jsonable_encoder

from ..utils.invoice_processor import preprocess_invoices
from ..utils.json_utils import dataframe_to_json_records
from .response_service import (
    _no_reply_result,
    _build_decision,
    classify_reply,
    decide_final_action,
    extract_reply_text,
    find_latest_reply,
    generate_email_content,
)


logger = logging.getLogger(__name__)

STAGE_ORDER = ["initial", "first", "second", "third", "escalation"]


def run_collection_workflow(
    raw_df: pd.DataFrame,
    customer_replies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    End-to-end AR collection workflow:

    1. Preprocess raw AR records — filter to valid overdue invoices only.
    2. Split into eligible (matching a reminder stage) and ignored (outside rules).
    3. For eligible invoices only: match replies, classify, decide action, generate email.
    4. For ignored invoices: record final_action=ignored without any AI calls.
    5. Build response outputs for all sections.

    Ineligible invoices are recorded in final_actions with action=ignored but are
    intentionally excluded from response_classification (no reply processing needed).
    """

    replies = customer_replies or []
    invoices_df, skipped_df = preprocess_invoices(raw_df)

    eligible_df = _get_eligible(invoices_df)
    ignored_df = _get_ignored(invoices_df)

    logger.info(
        "Workflow started: %d raw records → %d valid overdue, %d eligible, %d ignored, %d skipped.",
        len(raw_df), len(invoices_df), len(eligible_df), len(ignored_df), len(skipped_df),
    )

    response_rows: list[dict[str, Any]] = []
    final_action_rows: list[dict[str, Any]] = []

    # ── Process eligible invoices (reply matching + AI classification + email) ──
    for _, invoice in eligible_df.iterrows():
        reply = find_latest_reply(invoice, replies)
        reply_text = extract_reply_text(reply)

        classification = classify_reply(reply_text)
        decision = decide_final_action(invoice, classification)
        email = generate_email_content(invoice, classification, decision)

        # Response classification only records invoices that had a reply
        if reply:
            response_rows.append(
                _build_response_row(
                    invoice=invoice,
                    reply=reply,
                    reply_text=reply_text,
                    classification=classification,
                )
            )

        final_action_rows.append(
            _build_final_action_row(
                invoice=invoice,
                classification=classification,
                decision=decision,
                email=email,
            )
        )

    # ── Record ignored invoices without AI calls ──────────────────────────────
    for _, invoice in ignored_df.iterrows():
        decision = _build_decision(
            final_action="ignored",
            human_review=False,
            reason="Invoice is outside the defined reminder aging rules.",
        )

        final_action_rows.append(
            _build_final_action_row(
                invoice=invoice,
                classification=_no_reply_result(),
                decision=decision,
                email={"email_subject": "", "email_body": ""},
            )
        )

    response_df = pd.DataFrame(response_rows)
    final_action_df = pd.DataFrame(final_action_rows)

    logger.info(
        "Workflow complete: %d sent, %d drafted, %d ignored.",
        _count_action(final_action_df, "sent"),
        _count_action(final_action_df, "drafted_for_review"),
        _count_action(final_action_df, "ignored"),
    )

    result = {
        "summary": _build_summary(
            raw_df=raw_df,
            invoices_df=invoices_df,
            eligible_df=eligible_df,
            ignored_df=ignored_df,
            skipped_df=skipped_df,
            replies=replies,
            response_df=response_df,
            final_action_df=final_action_df,
        ),
        "stage_outputs": _build_stage_outputs(invoices_df),
        "reminder_eligibility": dataframe_to_json_records(invoices_df),
        "response_classification": dataframe_to_json_records(response_df),
        "final_actions": dataframe_to_json_records(final_action_df),
        "skipped_records": dataframe_to_json_records(skipped_df),
        "sample_normal_email": _get_sample_email(
            final_action_df, "sent", exclude_stage="escalation"
        ),
        "sample_escalation_email": _get_sample_email(
            final_action_df, "sent", include_stage="escalation"
        ),
        "assumptions": [
            "Reply JSON upload is optional. When omitted, all eligible invoices are treated as no_reply.",
            "No real emails are sent. final_action='sent' means send-ready output in test mode.",
            "Gemini is used only for reply classification, summarisation, and email wording.",
            "Business decisions (sent / drafted / ignored) are always rule-based — never AI-driven.",
            "Only eligible invoices (matching a defined aging rule) are processed for replies and emails.",
            "Ineligible invoices (outside exact aging rules) are marked ignored without Gemini calls.",
            "Response classification output contains only invoices where a customer reply was found.",
            "human_review_required is set by rule after classification, never by AI output.",
        ],
    }

    return jsonable_encoder(result)


# ── DataFrame helpers ─────────────────────────────────────────────────────────

def _get_eligible(invoices_df: pd.DataFrame) -> pd.DataFrame:
    if invoices_df.empty:
        return pd.DataFrame()

    return invoices_df[invoices_df["is_eligible_for_reminder"] == True].copy()


def _get_ignored(invoices_df: pd.DataFrame) -> pd.DataFrame:
    if invoices_df.empty:
        return pd.DataFrame()

    return invoices_df[invoices_df["is_eligible_for_reminder"] == False].copy()


def _count_action(final_action_df: pd.DataFrame, action: str) -> int:
    if final_action_df.empty or "final_action" not in final_action_df.columns:
        return 0

    return int((final_action_df["final_action"] == action).sum())


# ── Summary builder ───────────────────────────────────────────────────────────

def _build_summary(
    raw_df: pd.DataFrame,
    invoices_df: pd.DataFrame,
    eligible_df: pd.DataFrame,
    ignored_df: pd.DataFrame,
    skipped_df: pd.DataFrame,
    replies: list[dict[str, Any]],
    response_df: pd.DataFrame,
    final_action_df: pd.DataFrame,
) -> dict[str, Any]:
    action_counts = (
        final_action_df["final_action"].value_counts().to_dict()
        if not final_action_df.empty
        else {}
    )

    return {
        "raw_records": len(raw_df),
        "valid_overdue_invoices": len(invoices_df),
        "eligible_reminders": len(eligible_df),
        "ignored_outside_reminder_rules": len(ignored_df),
        "skipped_records": len(skipped_df),
        "reply_records_uploaded": len(replies),
        "response_records_processed": len(response_df),
        "final_action_counts": action_counts,
    }


# ── Stage outputs ─────────────────────────────────────────────────────────────

def _build_stage_outputs(
    invoices_df: pd.DataFrame,
) -> dict[str, list[dict[str, Any]]]:
    outputs: dict[str, list[dict[str, Any]]] = {}

    for stage in STAGE_ORDER:
        if invoices_df.empty:
            stage_df = pd.DataFrame()
        else:
            stage_df = invoices_df[invoices_df["reminder_stage"] == stage]

        outputs[stage] = dataframe_to_json_records(stage_df)

    return outputs


# ── Row builders ──────────────────────────────────────────────────────────────

def _build_response_row(
    invoice: pd.Series,
    reply: dict[str, Any],
    reply_text: str,
    classification: dict[str, Any],
) -> dict[str, Any]:
    return {
        "document_number": invoice.get("document_number"),
        "customer_name": invoice.get("customer_name"),
        "customer_email": invoice.get("customer_email"),
        "has_reply": True,
        "reply_received_date": reply.get("received_date", ""),
        "reply_text": reply_text,
        "classification": classification.get("classification"),
        "summary": classification.get("summary"),
        "key_reason": classification.get("key_reason"),
        "promised_payment_date": classification.get("promised_payment_date"),
        "requested_action": classification.get("requested_action"),
        "human_review_required": classification.get("human_review_required"),
        "confidence": classification.get("confidence"),
    }


def _build_final_action_row(
    invoice: pd.Series,
    classification: dict[str, Any],
    decision: dict[str, Any],
    email: dict[str, str],
) -> dict[str, Any]:
    return {
        "document_number": invoice.get("document_number"),
        "customer_name": invoice.get("customer_name"),
        "customer_email": invoice.get("customer_email"),
        "invoice_amount": invoice.get("invoice_amount"),
        "due_date": invoice.get("due_date"),
        "aging_days": invoice.get("aging_days"),
        "reminder_stage": invoice.get("reminder_stage"),
        "reminder_stage_label": invoice.get("reminder_stage_label"),
        "classification": classification.get("classification"),
        "response_summary": classification.get("summary"),
        "human_review_required": decision.get("human_review_required"),
        "final_action": decision.get("final_action"),
        "action_reason": decision.get("action_reason"),
        "email_subject": email.get("email_subject"),
        "email_body": email.get("email_body"),
    }


# ── Sample email selector ─────────────────────────────────────────────────────

def _get_sample_email(
    final_action_df: pd.DataFrame,
    action: str,
    include_stage: str | None = None,
    exclude_stage: str | None = None,
) -> dict[str, str]:
    empty: dict[str, str] = {"email_subject": "", "email_body": ""}

    if final_action_df.empty:
        return empty

    sample_df = final_action_df[final_action_df["final_action"] == action]

    if include_stage:
        sample_df = sample_df[sample_df["reminder_stage"] == include_stage]

    if exclude_stage:
        sample_df = sample_df[sample_df["reminder_stage"] != exclude_stage]

    if sample_df.empty:
        return empty

    row = sample_df.iloc[0]

    return {
        "email_subject": row.get("email_subject", ""),
        "email_body": row.get("email_body", ""),
    }