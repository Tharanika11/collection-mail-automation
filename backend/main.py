from pathlib import Path

import pandas as pd

from data_loader import load_ar_excel, load_customer_replies
from decision_engine import decide_final_action
from email_response_checker import find_customer_reply
from email_template import generate_email_template
from logger import setup_logger
from preprocessor import preprocess_invoices
from reminder_rules import apply_reminder_rules
from response_classifier import classify_response


def main() -> None:
    """
    Main workflow:
    1. Load Excel data
    2. Preprocess invoices
    3. Apply reminder eligibility rules
    4. Check sample customer replies
    5. Classify replies
    6. Decide final actions
    7. Generate email templates
    8. Save CSV outputs
    """

    project_root = Path(__file__).resolve().parents[1]

    data_file = project_root / "data" / "synthetic_customer_ar_data.xlsx"
    replies_file = project_root / "sample_emails" / "customer_replies.json"
    output_dir = project_root / "output"

    output_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(project_root)

    logger.info("Starting Collections Email Automation workflow")

    try:
        # Step 1: Load AR Excel data
        raw_df = load_ar_excel(data_file)
        logger.info(f"Loaded Excel data with {len(raw_df)} rows")

        # Step 2: Preprocess and validate data
        valid_invoices_df, skipped_df = preprocess_invoices(raw_df)
        logger.info(f"Valid invoices: {len(valid_invoices_df)}")
        logger.info(f"Skipped records: {len(skipped_df)}")

        # Step 3: Apply reminder rules
        reminder_df = apply_reminder_rules(valid_invoices_df)
        eligible_df = reminder_df[reminder_df["is_eligible_for_reminder"] == True]

        logger.info(f"Eligible reminders: {len(eligible_df)}")

        # Output 1: Reminder eligibility
        reminder_output_path = output_dir / "reminder_eligibility.csv"
        reminder_df.to_csv(reminder_output_path, index=False)
        logger.info(f"Saved reminder eligibility output: {reminder_output_path}")

        # Optional skipped output
        if not skipped_df.empty:
            skipped_output_path = output_dir / "skipped_records.csv"
            skipped_df.to_csv(skipped_output_path, index=False)
            logger.info(f"Saved skipped records output: {skipped_output_path}")

        # Step 4: Load sample customer replies
        customer_replies = load_customer_replies(replies_file)
        logger.info(f"Loaded {len(customer_replies)} sample customer replies")

        classification_rows = []
        final_action_rows = []

        # Step 5-8: Process each invoice
        for _, invoice in reminder_df.iterrows():
            customer_reply = find_customer_reply(invoice, customer_replies)

            reply_text = ""
            reply_received_date = ""

            if customer_reply:
                reply_text = customer_reply.get("reply", "")
                reply_received_date = customer_reply.get("received_date", "")

            classification_result = classify_response(reply_text)
            decision_result = decide_final_action(invoice, classification_result)
            email_result = generate_email_template(
                invoice,
                decision_result["final_action"]
            )

            classification_rows.append({
                "document_number": invoice.get("document_number"),
                "customer_name": invoice.get("customer_name"),
                "customer_email": invoice.get("customer_email"),
                "has_reply": bool(customer_reply),
                "reply_received_date": reply_received_date,
                "reply_text": reply_text,
                "classification": classification_result.get("classification"),
                "classification_summary": classification_result.get("summary"),
                "confidence": classification_result.get("confidence"),
                "human_review_required": classification_result.get("human_review_required"),
                "review_reason": classification_result.get("review_reason")
            })

            final_action_rows.append({
                "document_number": invoice.get("document_number"),
                "customer_name": invoice.get("customer_name"),
                "customer_email": invoice.get("customer_email"),
                "invoice_amount": invoice.get("invoice_amount"),
                "due_date": invoice.get("due_date"),
                "aging_days": invoice.get("aging_days"),
                "reminder_stage": invoice.get("reminder_stage"),
                "reminder_stage_label": invoice.get("reminder_stage_label"),
                "classification": classification_result.get("classification"),
                "final_action": decision_result.get("final_action"),
                "action_reason": decision_result.get("action_reason"),
                "human_review_required": decision_result.get("human_review_required"),
                "should_generate_email": decision_result.get("should_generate_email"),
                "email_subject": email_result.get("email_subject"),
                "email_body": email_result.get("email_body")
            })

        # Output 2: Response classification
        classification_df = pd.DataFrame(classification_rows)
        classification_output_path = output_dir / "response_classification.csv"
        classification_df.to_csv(classification_output_path, index=False)
        logger.info(f"Saved response classification output: {classification_output_path}")

        # Output 3: Final actions
        final_actions_df = pd.DataFrame(final_action_rows)
        final_actions_output_path = output_dir / "final_actions.csv"
        final_actions_df.to_csv(final_actions_output_path, index=False)
        logger.info(f"Saved final actions output: {final_actions_output_path}")

        logger.info("Workflow completed successfully")

        print("\nCollections Email Automation Completed")
        print("--------------------------------------")
        print(f"Total records loaded      : {len(raw_df)}")
        print(f"Valid invoices            : {len(valid_invoices_df)}")
        print(f"Skipped records           : {len(skipped_df)}")
        print(f"Eligible reminders        : {len(eligible_df)}")
        print(f"Output folder             : {output_dir}")

    except Exception as error:
        logger.exception(f"Workflow failed: {error}")
        print(f"\nError: {error}")


if __name__ == "__main__":
    main()