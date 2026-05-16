import logging
import re
from typing import Any

import pandas as pd

from .gemini_service import generate_json


logger = logging.getLogger(__name__)

CLASSIFICATIONS = [
    "payment_made",
    "payment_promised",
    "dispute",
    "copy_request",
    "ooo_bounce",
    "no_meaningful",
    "no_reply",
]

# Classifications that always require human review before sending
CLASSIFICATIONS_REQUIRING_REVIEW = {
    "payment_made",
    "payment_promised",
    "dispute",
    "copy_request",
    "ooo_bounce",
    "no_meaningful",
}

CONFIDENCE_LEVELS = ["high", "medium", "low"]

# human_review_required is intentionally excluded from the AI schema.
# It is always set by rule after classification, never by AI,
# so that the business decision remains deterministic and auditable.
CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "classification": {"type": "string", "enum": CLASSIFICATIONS},
        "summary": {"type": "string"},
        "key_reason": {"type": "string"},
        "promised_payment_date": {"type": "string"},
        "requested_action": {"type": "string"},
        "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
    },
    "required": [
        "classification",
        "summary",
        "key_reason",
        "promised_payment_date",
        "requested_action",
        "confidence",
    ],
}

EMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "email_subject": {"type": "string"},
        "email_body": {"type": "string"},
    },
    "required": ["email_subject", "email_body"],
}

# Rule table: (classification, patterns, summary, key_reason, requested_action, confidence)
RULE_DEFINITIONS = [
    (
        "ooo_bounce",
        [
            r"\bout of office\b",
            r"\bautomatic reply\b",
            r"\bauto.reply\b",
            r"\bdelivery failed\b",
            r"\bbounce\b",
            r"\bundeliverable\b",
            r"\binvalid email\b",
        ],
        "Customer appears to be unavailable or the email may have bounced.",
        "Email/contact issue.",
        "Verify contact details or wait for customer to become available.",
        "high",
    ),
    (
        "dispute",
        [
            r"\bincorrect\b",
            r"\bwrong\b",
            r"\bissue\b",
            r"\bdispute\b",
            r"\bamount is wrong\b",
            r"\bpo mismatch\b",
            r"\btax issue\b",
            r"\bnot received\b",
            r"\bclarify\b",
            r"\bclarification\b",
        ],
        "Customer raised a dispute or query about the invoice.",
        "Invoice dispute or query.",
        "Review the customer query and resolve before sending a reminder.",
        "high",
    ),
    (
        "copy_request",
        [
            r"\binvoice copy\b",
            r"\bcopy of invoice\b",
            r"\bresend\b",
            r"\bsend a copy\b",
            r"\bstatement\b",
            r"\bsupporting document\b",
            r"\bsupporting documents\b",
        ],
        "Customer requested an invoice copy, statement, or supporting document.",
        "Documentation requested.",
        "Provide the requested document before continuing collection follow-up.",
        "high",
    ),
    (
        "no_meaningful",
        [
            r"\bnot paid\b",
            r"\bunpaid\b",
            r"\bhas not been paid\b",
            r"\bhave not paid\b",
            r"\bpayment not completed\b",
            r"\bpayment has not been made\b",
        ],
        "Customer indicates payment has not been made but provided no resolution.",
        "Payment not completed.",
        "Review manually before sending further communication.",
        "medium",
    ),
    (
        "payment_made",
        [
            r"\balready paid\b",
            r"\bwe have paid\b",
            r"\bwe paid\b",
            r"\bi have paid\b",
            r"\bpayment has been made\b",
            r"\bpayment completed\b",
            r"\bpayment processed\b",
            r"\bsettled\b",
            r"\bremittance attached\b",
            r"\btransfer completed\b",
        ],
        "Customer claims the payment has already been made.",
        "Payment claim requires reconciliation.",
        "Verify payment in the accounting system before sending another reminder.",
        "medium",
    ),
    (
        "payment_promised",
        [
            r"\bwill pay\b",
            r"\bwe will pay\b",
            r"\bi will pay\b",
            r"\bpromise\b",
            r"\bnext week\b",
            r"\btomorrow\b",
            r"\bby friday\b",
            r"\bsoon\b",
            r"\barrange payment\b",
            r"\bpayment will be made\b",
        ],
        "Customer promised to pay at a later date.",
        "Payment promise requires follow-up.",
        "Track the promised payment date and verify before further escalation.",
        "medium",
    ),
]

# Stage-specific tone guidance injected into email prompts
_STAGE_TONE_GUIDANCE = {
    "initial": (
        "This is the first reminder. Use a polite, friendly tone. "
        "Assume the customer may have overlooked the invoice."
    ),
    "first": (
        "This is the second contact. Use a professional, neutral tone. "
        "Politely emphasise that the invoice is now overdue."
    ),
    "second": (
        "This is the third contact. Use a firm but professional tone. "
        "Make clear that prompt payment is expected."
    ),
    "third": (
        "This is the fourth contact. Use a firm tone. "
        "Mention that escalation will follow if payment is not received promptly."
    ),
    "escalation": (
        "This is an escalation. Use a firm, serious tone. "
        "State clearly that further action (referral to collections or legal) may follow "
        "if the account is not resolved. Remain professional and factual."
    ),
}


# ── Reply matching ────────────────────────────────────────────────────────────

def find_latest_reply(
    invoice: pd.Series,
    customer_replies: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Matches replies to a specific invoice using invoice number as the primary key.

    Matching rule (AND logic — both conditions must be satisfied):
    - Invoice number must appear in the reply's invoice field, subject, or body.
    - Customer email must match when both sides have an email (optional confirmation).

    Using OR was a bug: it caused one reply from a shared customer email to match
    every invoice belonging to that customer regardless of invoice number.
    """

    invoice_number = normalize_text(invoice.get("document_number"))
    customer_email = normalize_email(invoice.get("customer_email"))

    if not invoice_number:
        return None

    matches: list[dict[str, Any]] = []

    for reply in customer_replies:
        reply_invoice = normalize_text(
            reply.get("document_number")
            or reply.get("invoice_number")
            or reply.get("invoice")
        )
        reply_email = normalize_email(
            reply.get("customer_email")
            or reply.get("from")
            or reply.get("sender")
            or reply.get("sender_email")
        )
        reply_subject = normalize_text(reply.get("subject", ""))
        reply_body = normalize_text(
            reply.get("reply") or reply.get("body") or reply.get("message") or ""
        )

        # Primary: invoice number must be referenced in the reply
        invoice_referenced = (
            reply_invoice == invoice_number
            or invoice_number in reply_subject
            or invoice_number in reply_body
        )

        if not invoice_referenced:
            continue

        # Secondary: if both sides have an email, they must match
        email_consistent = (
            not reply_email
            or not customer_email
            or reply_email == customer_email
        )

        if email_consistent:
            matches.append(reply)

    if not matches:
        return None

    # Return the most recently received reply
    matches.sort(key=_reply_sort_date, reverse=True)
    return matches[0]


def _reply_sort_date(reply: dict[str, Any]) -> pd.Timestamp:
    raw = reply.get("received_date") or reply.get("date") or reply.get("created_at") or ""
    parsed = pd.to_datetime(raw, errors="coerce")
    return pd.Timestamp.min if pd.isna(parsed) else parsed


# ── Classification ────────────────────────────────────────────────────────────

def classify_reply(reply_text: str | None) -> dict[str, Any]:
    """
    Classifies a customer reply.
    Uses Gemini when available; falls back to rule-based logic.
    human_review_required is always set by rule, never by AI.
    """

    if not reply_text or not reply_text.strip():
        return _no_reply_result()

    gemini_result = generate_json(
        prompt=build_classification_prompt(reply_text),
        response_schema=CLASSIFICATION_SCHEMA,
    )

    if gemini_result:
        return _apply_review_rule(validate_classification(gemini_result))

    logger.debug("Using rule-based classification fallback.")
    return classify_reply_with_rules(reply_text)


def build_classification_prompt(reply_text: str) -> str:
    return f"""
You are an accounts receivable response classifier.

Classify the customer reply into exactly one classification:
- payment_made
- payment_promised
- dispute
- copy_request
- ooo_bounce
- no_meaningful
- no_reply

Return:
- classification
- summary: short business-friendly summary (1-2 sentences)
- key_reason: the specific reason or claim made
- promised_payment_date: date or phrase if mentioned, empty string otherwise
- requested_action: what the AR team should do next
- confidence: high / medium / low

Important rules:
- If the customer says payment is not completed, do NOT classify as payment_made.
- If dispute or query wording appears alongside payment wording, classify as dispute.
- If the intent is unclear, classify as no_meaningful.
- Do not claim payment has been verified.

Customer reply:
\"\"\"{reply_text}\"\"\"
"""


def validate_classification(result: dict[str, Any]) -> dict[str, Any]:
    classification = result.get("classification", "no_meaningful")
    confidence = result.get("confidence", "low")

    if classification not in CLASSIFICATIONS:
        logger.warning("Gemini returned unknown classification '%s'; defaulting to no_meaningful.", classification)
        classification = "no_meaningful"

    if confidence not in CONFIDENCE_LEVELS:
        confidence = "low"

    return {
        "classification": classification,
        "summary": result.get("summary", "Reply reviewed."),
        "key_reason": result.get("key_reason", ""),
        "promised_payment_date": result.get("promised_payment_date", ""),
        "requested_action": result.get("requested_action", ""),
        "confidence": confidence,
    }


def classify_reply_with_rules(reply_text: str) -> dict[str, Any]:
    text = normalize_text(reply_text)

    for classification, patterns, summary, reason, action, confidence in RULE_DEFINITIONS:
        if any(re.search(pattern, text) for pattern in patterns):
            result = {
                "classification": classification,
                "summary": summary,
                "key_reason": reason,
                "promised_payment_date": extract_promised_date_hint(text),
                "requested_action": action,
                "confidence": confidence,
            }
            return _apply_review_rule(result)

    return _apply_review_rule({
        "classification": "no_meaningful",
        "summary": "Reply does not clearly explain payment status or required action.",
        "key_reason": "Unclear reply.",
        "promised_payment_date": "",
        "requested_action": "Review manually before sending a reminder.",
        "confidence": "low",
    })


def _apply_review_rule(result: dict[str, Any]) -> dict[str, Any]:
    """
    Sets human_review_required by rule.
    This field is never trusted from AI output — it is always derived here
    so that the decision is deterministic and auditable.
    """
    classification = result.get("classification", "no_meaningful")
    result["human_review_required"] = classification in CLASSIFICATIONS_REQUIRING_REVIEW
    return result


def _no_reply_result() -> dict[str, Any]:
    return {
        "classification": "no_reply",
        "summary": "No customer response was found for this invoice.",
        "key_reason": "No reply matched this invoice.",
        "promised_payment_date": "",
        "requested_action": "",
        "human_review_required": False,
        "confidence": "high",
    }


# ── Final action decision ─────────────────────────────────────────────────────

def decide_final_action(
    invoice: pd.Series,
    classification: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic decisioning. Gemini is never used here.
    Only eligible invoices with no reply (or a non-blocking reply) are sent automatically.
    """

    if not invoice.get("is_eligible_for_reminder"):
        return _build_decision(
            final_action="ignored",
            human_review=False,
            reason="Invoice is outside the defined reminder aging rules.",
        )

    classification_name = classification.get("classification")

    if classification_name == "no_reply":
        return _build_decision(
            final_action="sent",
            human_review=False,
            reason="Invoice is eligible and no customer response was found.",
        )

    if classification.get("human_review_required", True):
        return _build_decision(
            final_action="drafted_for_review",
            human_review=True,
            reason=(
                f"Customer response classified as '{classification_name}'; "
                "human review is required before sending."
            ),
        )

    # Reached only when a reply was found but human_review_required is False.
    # Currently this cannot happen given CLASSIFICATIONS_REQUIRING_REVIEW covers
    # all non-no_reply cases, but is kept for forward compatibility.
    return _build_decision(
        final_action="sent",
        human_review=False,
        reason="Reply does not block the reminder flow.",
    )


def _build_decision(
    final_action: str,
    human_review: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "final_action": final_action,
        "human_review_required": human_review,
        "action_reason": reason,
    }


# ── Email generation ──────────────────────────────────────────────────────────

def generate_email_content(
    invoice: pd.Series,
    classification: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, str]:
    if decision["final_action"] == "ignored":
        return {"email_subject": "", "email_body": ""}

    gemini_result = generate_json(
        prompt=build_email_prompt(invoice, classification, decision),
        response_schema=EMAIL_SCHEMA,
    )

    if gemini_result:
        return {
            "email_subject": gemini_result.get("email_subject", ""),
            "email_body": gemini_result.get("email_body", ""),
        }

    logger.debug("Using fallback email template for invoice %s.", invoice.get("document_number"))
    return fallback_email(invoice, classification, decision)


def build_email_prompt(
    invoice: pd.Series,
    classification: dict[str, Any],
    decision: dict[str, Any],
) -> str:
    email_type = "draft for human review" if decision["human_review_required"] else "send-ready reminder"
    stage = invoice.get("reminder_stage", "escalation")
    tone_guidance = _STAGE_TONE_GUIDANCE.get(stage, _STAGE_TONE_GUIDANCE["escalation"])

    return f"""
You are an accounts receivable assistant writing a collection reminder email.

Email type: {email_type}

Tone guidance: {tone_guidance}

Invoice details:
- Customer: {invoice.get("customer_name")}
- Invoice Number: {invoice.get("document_number")}
- Outstanding Amount: {invoice.get("invoice_amount")}
- Due Date: {invoice.get("due_date")}
- Aging Days: {invoice.get("aging_days")}
- Reminder Stage: {invoice.get("reminder_stage_label")}

Customer response context:
- Classification: {classification.get("classification")}
- Summary: {classification.get("summary")}
- Key Reason: {classification.get("key_reason")}
- Requested Action: {classification.get("requested_action")}
- Promised Payment Date: {classification.get("promised_payment_date")}

Rules:
- Follow the tone guidance exactly.
- Keep the email concise and professional.
- Do not claim that payment has been verified.
- If this is a draft for review, add a short internal note at the top explaining the context.
- Sign off as "Accounts Receivable Team".
- Return only valid JSON with email_subject and email_body.
"""


def fallback_email(
    invoice: pd.Series,
    classification: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, str]:
    document_number = invoice.get("document_number", "")
    stage = invoice.get("reminder_stage_label", "Reminder")
    context_note = ""

    if decision["human_review_required"]:
        context_note = (
            f"\n\n[Internal context note: "
            f"Customer response classified as '{classification.get('classification')}'. "
            f"{classification.get('summary', '')} "
            f"Suggested action: {classification.get('requested_action', '')}]"
        )

    return {
        "email_subject": f"{stage}: Invoice {document_number}",
        "email_body": (
            f"Dear {invoice.get('customer_name')},\n\n"
            f"This is a reminder regarding invoice {document_number}.\n\n"
            f"Outstanding Amount: {invoice.get('invoice_amount')}\n"
            f"Due Date: {invoice.get('due_date')}\n"
            f"Reminder Stage: {stage}"
            f"{context_note}\n\n"
            "Please arrange payment at your earliest convenience. "
            "If payment has already been made or if you have any queries, "
            "please reply to this email.\n\n"
            "Best regards,\n"
            "Accounts Receivable Team"
        ),
    }


# ── Utility helpers ───────────────────────────────────────────────────────────

def extract_reply_text(reply: dict[str, Any] | None) -> str:
    if not reply:
        return ""

    return str(
        reply.get("reply") or reply.get("body") or reply.get("message") or reply.get("content") or ""
    )


def extract_promised_date_hint(text: str) -> str:
    date_words = [
        "today", "tomorrow", "next week", "by friday",
        "monday", "tuesday", "wednesday", "thursday", "friday",
    ]

    for word in date_words:
        if word in text:
            return word

    return ""


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value).strip().lower())


def normalize_email(value: Any) -> str:
    text = normalize_text(value)

    match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    return match.group(0) if match else text