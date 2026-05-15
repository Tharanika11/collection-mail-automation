import json
import sys
from io import BytesIO
from pathlib import Path
import traceback
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

CURRENT_DIR = Path(__file__).resolve().parent

if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from preprocessor import preprocess_invoices
from reminder_rules import apply_reminder_rules
from email_response_checker import find_customer_reply
from response_classifier import classify_response
from decision_engine import decide_final_action
from email_template import generate_email_template


app = FastAPI(
    title="Collections Email Automation API",
    description="FastAPI backend for React-based collections automation UI",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def clean_value(value: Any) -> Any:
    """
    Converts Pandas/Numpy values into JSON-safe values.
    """

    if pd.isna(value):
        return ""

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def clean_dataframe_for_json(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Converts a Pandas DataFrame into a JSON-safe list of dictionaries.
    """

    if df is None or df.empty:
        return []

    records = df.to_dict(orient="records")

    cleaned_records = []

    for record in records:
        cleaned_record = {}

        for key, value in record.items():
            cleaned_record[key] = clean_value(value)

        cleaned_records.append(cleaned_record)

    return cleaned_records


def run_workflow(
    raw_df: pd.DataFrame,
    customer_replies: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Runs the complete collections automation workflow.

    Steps:
    1. Preprocess invoice records
    2. Apply reminder rules
    3. Check customer replies
    4. Classify responses
    5. Decide final actions
    6. Generate email templates
    """

    valid_invoices_df, skipped_df = preprocess_invoices(raw_df)

    reminder_df = apply_reminder_rules(valid_invoices_df)

    if reminder_df.empty:
        eligible_df = pd.DataFrame()
    else:
        eligible_df = reminder_df[
            reminder_df["is_eligible_for_reminder"] == True
        ]

    classification_rows = []
    final_action_rows = []

    # for _, invoice in reminder_df.iterrows():
    for _, invoice in eligible_df.iterrows():
        customer_reply = find_customer_reply(invoice, customer_replies)

        reply_text = ""
        reply_received_date = ""

        if customer_reply:
            reply_text = customer_reply.get("reply", "")
            reply_received_date = customer_reply.get("received_date", "")

        classification_result = classify_response(reply_text)

        decision_result = decide_final_action(
            invoice,
            classification_result
        )

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

    classification_df = pd.DataFrame(classification_rows)
    final_actions_df = pd.DataFrame(final_action_rows)

    result = {
        "summary": {
            "total_records": len(raw_df),
            "valid_invoices": len(valid_invoices_df),
            "skipped_records": len(skipped_df),
            "eligible_reminders": len(eligible_df),
            "sample_replies": len(customer_replies)
        },
        "reminder_eligibility": clean_dataframe_for_json(reminder_df),
        "response_classification": clean_dataframe_for_json(classification_df),
        "final_actions": clean_dataframe_for_json(final_actions_df),
        "skipped_records": clean_dataframe_for_json(skipped_df)
    }

    return jsonable_encoder(result)


@app.get("/")
def health_check():
    """
    Simple health-check endpoint.
    """

    return {
        "message": "Collections Email Automation API is running"
    }


@app.post("/run-workflow")
async def run_collections_workflow(
    excel_file: UploadFile = File(...),
    replies_file: UploadFile | None = File(None)
):
    """
    Receives:
    - Excel file from React frontend
    - Optional customer replies JSON file

    Returns:
    - Summary
    - Reminder eligibility rows
    - Response classification rows
    - Final action rows
    - Skipped records
    """

    try:
        excel_content = await excel_file.read()

        if not excel_content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded Excel file is empty."
            )

        try:
            raw_df = pd.read_excel(
                BytesIO(excel_content),
                engine="openpyxl"
            )
        except Exception as error:
            raise HTTPException(
                status_code=400,
                detail=f"Could not read Excel file. Please upload a valid .xlsx file. Error: {str(error)}"
            )

        customer_replies = []

        if replies_file is not None:
            replies_content = await replies_file.read()

            if replies_content:
                try:
                    customer_replies = json.loads(
                        replies_content.decode("utf-8")
                    )
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid JSON file. Please upload a valid customer replies JSON file."
                    )

                if not isinstance(customer_replies, list):
                    raise HTTPException(
                        status_code=400,
                        detail="Customer replies JSON must contain a list of reply objects."
                    )

        result = run_workflow(
            raw_df=raw_df,
            customer_replies=customer_replies
        )

        return result

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Workflow failed: {str(error)}"
        )
    
    except Exception as error:

     raise HTTPException(
        status_code=500,
        detail=traceback.format_exc()
    )