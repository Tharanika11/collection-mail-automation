from typing import Any
import os
import json
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types # type: ignore

load_dotenv()

ALLOWED_CLASSIFICATIONS = {
    "payment_made",
    "payment_promised",
    "dispute",
    "copy_request",
    "ooo_bounce",
    "no_meaningful",
    "no_reply",
}

ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def classify_response(reply_text: str | None) -> dict[str, Any]:
    """
    Classifies customer reply using Gemini first.
    If Gemini is disabled, missing, or fails, falls back to rule-based logic.
    """

    if not reply_text or not reply_text.strip():
        return {
            "classification": "no_reply",
            "summary": "No customer reply was found.",
            "human_review_required": False,
            "review_reason": "",
            "confidence": "high",
        }

    use_gemini = os.getenv("USE_GEMINI", "false").lower() == "true"
    api_key = os.getenv("GEMINI_API_KEY")

    if use_gemini and api_key:
        try:
            return classify_with_gemini(reply_text)
        except Exception as e:
            print(f"Gemini classification failed. Falling back to rules. Error: {e}")

    return classify_with_rules(reply_text)


def classify_with_gemini(reply_text: str) -> dict[str, Any]:
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = f"""
You are an accounts receivable email response classifier.

Classify the customer reply into exactly one of these categories:

1. payment_made
Customer says payment has already been made, transferred, settled, processed, or remittance is attached.

2. payment_promised
Customer says they will pay later, arrange payment soon, pay tomorrow, next week, by Friday, etc.

3. dispute
Customer raises an issue, incorrect amount, wrong invoice, PO mismatch, tax issue, not received invoice, clarification needed, or any dispute.

4. copy_request
Customer asks for invoice copy, statement, supporting document, resend invoice, or similar.

5. ooo_bounce
Out of office, automatic reply, delivery failed, bounce, undeliverable, invalid email.

6. no_meaningful
Reply exists but does not clearly fit the above categories.

7. no_reply
No reply content is available.

Important rules:
- If the customer says "not paid", "has not been paid", or "payment not completed", do not classify as payment_made.
- If dispute and payment wording both appear, classify as dispute.
- If unsure, classify as no_meaningful and set human_review_required to true.

Customer reply:
\"\"\"{reply_text}\"\"\"
"""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "classification": {
                        "type": "string",
                        "enum": list(ALLOWED_CLASSIFICATIONS),
                    },
                    "summary": {"type": "string"},
                    "human_review_required": {"type": "boolean"},
                    "review_reason": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": list(ALLOWED_CONFIDENCE),
                    },
                },
                "required": [
                    "classification",
                    "summary",
                    "human_review_required",
                    "review_reason",
                    "confidence",
                ],
            },
        ),
    )

    result = json.loads(response.text)
    return validate_result(result)


def validate_result(result: dict[str, Any]) -> dict[str, Any]:
    classification = result.get("classification", "no_meaningful")
    confidence = result.get("confidence", "low")

    if classification not in ALLOWED_CLASSIFICATIONS:
        classification = "no_meaningful"

    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "low"

    return {
        "classification": classification,
        "summary": result.get("summary", "Reply classified by Gemini."),
        "human_review_required": bool(result.get("human_review_required", True)),
        "review_reason": result.get("review_reason", ""),
        "confidence": confidence,
    }


def classify_with_rules(reply_text: str) -> dict[str, Any]:
    text = normalize_text(reply_text)

    rules = [
        (
            "ooo_bounce",
            [
                r"\bout of office\b",
                r"\bautomatic reply\b",
                r"\bauto reply\b",
                r"\bdelivery failed\b",
                r"\bbounce\b",
                r"\bundeliverable\b",
                r"\binvalid email\b",
            ],
            "Customer appears to be out of office or the email may have bounced.",
            "Email delivery or customer availability should be checked manually.",
            "high",
        ),
        (
            "dispute",
            [
                r"\bincorrect\b",
                r"\bwrong\b",
                r"\bmistake\b",
                r"\bissue\b",
                r"\bdispute\b",
                r"\bnot correct\b",
                r"\bamount is wrong\b",
                r"\bpo mismatch\b",
                r"\btax issue\b",
                r"\bnot received\b",
                r"\bplease clarify\b",
            ],
            "Customer has raised an issue or dispute about the invoice.",
            "Invoice dispute needs manual review.",
            "high",
        ),
        (
            "copy_request",
            [
                r"\bsend invoice\b",
                r"\binvoice copy\b",
                r"\bcopy of invoice\b",
                r"\bresend\b",
                r"\bsend a copy\b",
                r"\bstatement\b",
                r"\bsupporting document\b",
            ],
            "Customer requested a copy of the invoice or statement.",
            "Invoice copy or supporting document should be provided before sending another reminder.",
            "high",
        ),
        (
            "no_meaningful",
            [
                r"\bnot paid\b",
                r"\bunpaid\b",
                r"\bhas not been paid\b",
                r"\bhave not paid\b",
                r"\bpayment has not been made\b",
                r"\bpayment not completed\b",
            ],
            "Customer indicates payment has not been made, but the reply does not provide a clear payment resolution.",
            "Customer says payment is not completed, so manual review is required.",
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
                r"\btransfer completed\b",
                r"\bremittance attached\b",
            ],
            "Customer says the payment has already been made.",
            "Payment claim should be verified through reconciliation before sending another reminder.",
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
            "Customer promised to make the payment later.",
            "Payment promise should be manually verified before sending another reminder.",
            "medium",
        ),
    ]

    for classification, patterns, summary, reason, confidence in rules:
        if contains_pattern(text, patterns):
            return {
                "classification": classification,
                "summary": summary,
                "human_review_required": classification != "no_reply",
                "review_reason": reason,
                "confidence": confidence,
            }

    return {
        "classification": "no_meaningful",
        "summary": "Reply does not contain clear payment-related information.",
        "human_review_required": True,
        "review_reason": "Reply is unclear and needs manual review.",
        "confidence": "low",
    }


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def contains_pattern(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)
