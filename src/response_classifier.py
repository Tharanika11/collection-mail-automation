from typing import Any
import re


def classify_response(reply_text: str | None) -> dict[str, Any]:
    """
    Classifies customer replies using safer rule-based logic.

    Categories:
    - payment_made
    - payment_promised
    - dispute
    - copy_request
    - ooo_bounce
    - no_meaningful
    - no_reply
    """

    if not reply_text or not reply_text.strip():
        return {
            "classification": "no_reply",
            "summary": "No customer reply was found.",
            "human_review_required": False,
            "review_reason": "",
            "confidence": "high"
        }

    text = normalize_text(reply_text)

    # 1. Out of office / bounce should be detected early
    if contains_pattern(text, [
        r"\bout of office\b",
        r"\bautomatic reply\b",
        r"\bauto reply\b",
        r"\bdelivery failed\b",
        r"\bmail delivery failed\b",
        r"\bbounce\b",
        r"\bundeliverable\b",
        r"\binvalid email\b"
    ]):
        return {
            "classification": "ooo_bounce",
            "summary": "Customer appears to be out of office or the email may have bounced.",
            "human_review_required": True,
            "review_reason": "Email delivery or customer availability should be checked manually.",
            "confidence": "high"
        }

    # 2. Dispute / query should be checked before payment-made
    # because customers may say things like "we have not paid because the amount is wrong"
    if contains_pattern(text, [
        r"\bincorrect\b",
        r"\bwrong\b",
        r"\bmistake\b",
        r"\bissue\b",
        r"\bdispute\b",
        r"\bdisputed\b",
        r"\bnot correct\b",
        r"\bamount is wrong\b",
        r"\bprice is wrong\b",
        r"\bpo mismatch\b",
        r"\btax issue\b",
        r"\bnot received\b",
        r"\bneed clarification\b",
        r"\bplease clarify\b"
    ]):
        return {
            "classification": "dispute",
            "summary": "Customer has raised an issue or dispute about the invoice.",
            "human_review_required": True,
            "review_reason": "Invoice dispute needs manual review.",
            "confidence": "high"
        }

    # 3. Copy / statement request
    if contains_pattern(text, [
        r"\bsend invoice\b",
        r"\binvoice copy\b",
        r"\bcopy of invoice\b",
        r"\bcopy of the invoice\b",
        r"\bresend\b",
        r"\bsend a copy\b",
        r"\bplease send the invoice\b",
        r"\bstatement\b",
        r"\bsupporting document\b"
    ]):
        return {
            "classification": "copy_request",
            "summary": "Customer requested a copy of the invoice or statement.",
            "human_review_required": True,
            "review_reason": "Invoice copy or supporting document should be provided before sending another reminder.",
            "confidence": "high"
        }

    # 4. Negative payment phrases should NOT be payment_made
    if contains_pattern(text, [
        r"\bnot paid\b",
        r"\bunpaid\b",
        r"\bhas not been paid\b",
        r"\bhave not paid\b",
        r"\bpayment has not been made\b",
        r"\bpayment was not made\b",
        r"\bpayment not completed\b"
    ]):
        return {
            "classification": "no_meaningful",
            "summary": "Customer indicates payment has not been made, but the reply does not provide a clear payment resolution.",
            "human_review_required": True,
            "review_reason": "Customer says payment is not completed, so manual review is required.",
            "confidence": "medium"
        }

    # 5. Payment already made - use specific phrases only
    if contains_pattern(text, [
        r"\balready paid\b",
        r"\bwe have paid\b",
        r"\bwe paid\b",
        r"\bi have paid\b",
        r"\bi paid\b",
        r"\bpayment has been made\b",
        r"\bpayment was made\b",
        r"\bpayment completed\b",
        r"\bpayment has been completed\b",
        r"\bpayment processed\b",
        r"\bpayment has been processed\b",
        r"\bsettled\b",
        r"\balready settled\b",
        r"\btransfer completed\b",
        r"\btransfer done\b",
        r"\balready transferred\b",
        r"\bbank transfer completed\b",
        r"\bremittance attached\b",
        r"\bremittance sent\b"
    ]):
        return {
            "classification": "payment_made",
            "summary": "Customer says the payment has already been made.",
            "human_review_required": True,
            "review_reason": "Payment claim should be verified through reconciliation before sending another reminder.",
            "confidence": "medium"
        }

    # 6. Payment promised - future payment wording
    if contains_pattern(text, [
        r"\bwill pay\b",
        r"\bwe will pay\b",
        r"\bi will pay\b",
        r"\bpromise\b",
        r"\bnext week\b",
        r"\btomorrow\b",
        r"\bby friday\b",
        r"\bby monday\b",
        r"\bsoon\b",
        r"\barrange payment\b",
        r"\bwill arrange payment\b",
        r"\bpayment will be made\b",
        r"\bpayment will be transferred\b",
        r"\bwill be transferred\b"
    ]):
        return {
            "classification": "payment_promised",
            "summary": "Customer promised to make the payment later.",
            "human_review_required": True,
            "review_reason": "Payment promise should be manually verified before sending another reminder.",
            "confidence": "medium"
        }

    # 7. Default unclear response
    return {
        "classification": "no_meaningful",
        "summary": "Reply does not contain clear payment-related information.",
        "human_review_required": True,
        "review_reason": "Reply is unclear and needs manual review.",
        "confidence": "low"
    }


def normalize_text(value: str) -> str:
    """
    Lowercase and normalize spaces.
    """
    return re.sub(r"\s+", " ", value.lower()).strip()


def contains_pattern(text: str, patterns: list[str]) -> bool:
    """
    Uses regex pattern matching instead of simple substring matching.
    """
    return any(re.search(pattern, text) for pattern in patterns)