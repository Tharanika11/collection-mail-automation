import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Make local src imports work safely
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from preprocessor import preprocess_invoices
from reminder_rules import apply_reminder_rules
from email_response_checker import find_customer_reply
from response_classifier import classify_response
from decision_engine import decide_final_action
from email_template import generate_email_template


# -------------------------------------------------------------------
# Page Configuration
# -------------------------------------------------------------------

st.set_page_config(
    page_title="Collections Email Automation",
    page_icon="📩",
    layout="wide"
)


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------

def load_excel(uploaded_file) -> pd.DataFrame:
    """
    Loads uploaded Excel file into a Pandas DataFrame.
    """

    return pd.read_excel(uploaded_file, engine="openpyxl")


def load_replies_from_upload(uploaded_file) -> list[dict[str, Any]]:
    """
    Loads customer replies from uploaded JSON file.
    """

    if uploaded_file is None:
        return []

    try:
        data = json.load(uploaded_file)

        if not isinstance(data, list):
            st.error("Customer replies JSON must contain a list of reply objects.")
            return []

        return data

    except Exception as error:
        st.error(f"Could not read customer replies JSON: {error}")
        return []


def load_default_replies() -> list[dict[str, Any]]:
    """
    Loads default sample_emails/customer_replies.json if it exists.
    """

    replies_path = PROJECT_ROOT / "sample_emails" / "customer_replies.json"

    if not replies_path.exists():
        return []

    try:
        with open(replies_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []


def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    """
    Converts a DataFrame to CSV bytes for Streamlit download button.
    """

    return df.to_csv(index=False).encode("utf-8")


def run_collections_workflow(
    raw_df: pd.DataFrame,
    customer_replies: list[dict[str, Any]],
    save_to_output: bool = True
) -> dict[str, Any]:
    """
    Runs the full collections automation workflow in memory.
    """

    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Preprocess invoice data
    valid_invoices_df, skipped_df = preprocess_invoices(raw_df)

    # Step 2: Apply reminder rules
    reminder_df = apply_reminder_rules(valid_invoices_df)

    if reminder_df.empty:
        eligible_df = pd.DataFrame()
    else:
        eligible_df = reminder_df[
            reminder_df["is_eligible_for_reminder"] == True
        ]

    classification_rows = []
    final_action_rows = []

    # Step 3: Process each invoice
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

    classification_df = pd.DataFrame(classification_rows)
    final_actions_df = pd.DataFrame(final_action_rows)

    # Step 4: Save outputs locally
    if save_to_output:
        reminder_df.to_csv(output_dir / "reminder_eligibility.csv", index=False)
        classification_df.to_csv(output_dir / "response_classification.csv", index=False)
        final_actions_df.to_csv(output_dir / "final_actions.csv", index=False)

        if not skipped_df.empty:
            skipped_df.to_csv(output_dir / "skipped_records.csv", index=False)

    return {
        "raw_df": raw_df,
        "valid_invoices_df": valid_invoices_df,
        "skipped_df": skipped_df,
        "reminder_df": reminder_df,
        "eligible_df": eligible_df,
        "classification_df": classification_df,
        "final_actions_df": final_actions_df,
        "output_dir": output_dir
    }


# -------------------------------------------------------------------
# UI Header
# -------------------------------------------------------------------

st.title("📩 Collections Email Automation")
st.caption("Python + Streamlit UI for rule-based AR reminder automation")

st.markdown(
    """
    This app reads an Accounts Receivable Excel file, validates invoice records,
    assigns reminder stages, checks sample customer replies, classifies responses,
    decides final actions, and generates downloadable CSV reports.
    """
)


# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Workflow Settings")

    st.markdown("### Reminder Rules")

    st.info(
        """
        4 days  → Initial Reminder  
        6 days  → 1st Reminder  
        8 days  → 2nd Reminder  
        10 days → 3rd Reminder  
        >10 days → Escalation
        """
    )

    save_to_output = st.checkbox(
        "Save generated CSV files into output folder",
        value=True
    )

    use_default_replies = st.checkbox(
        "Use default sample_emails/customer_replies.json",
        value=True
    )


# -------------------------------------------------------------------
# Upload Section
# -------------------------------------------------------------------

st.subheader("1. Upload Files")

col1, col2 = st.columns(2)

with col1:
    uploaded_excel = st.file_uploader(
        "Upload AR Excel File",
        type=["xlsx", "xls"]
    )

with col2:
    uploaded_replies = st.file_uploader(
        "Upload Customer Replies JSON Optional",
        type=["json"]
    )

st.markdown("---")


# -------------------------------------------------------------------
# Run Workflow
# -------------------------------------------------------------------

st.subheader("2. Run Automation")

run_button = st.button(
    "▶ Run Collections Automation",
    type="primary",
    disabled=uploaded_excel is None
)

if uploaded_excel is None:
    st.warning("Please upload the AR Excel file to start.")

if run_button:
    try:
        with st.spinner("Processing invoices..."):
            raw_df = load_excel(uploaded_excel)

            if uploaded_replies is not None:
                customer_replies = load_replies_from_upload(uploaded_replies)
            elif use_default_replies:
                customer_replies = load_default_replies()
            else:
                customer_replies = []

            results = run_collections_workflow(
                raw_df=raw_df,
                customer_replies=customer_replies,
                save_to_output=save_to_output
            )

            st.session_state["results"] = results
            st.session_state["customer_replies_count"] = len(customer_replies)

        st.success("Collections automation completed successfully.")

    except Exception as error:
        st.error(f"Workflow failed: {error}")


# -------------------------------------------------------------------
# Results Section
# -------------------------------------------------------------------

if "results" in st.session_state:
    results = st.session_state["results"]

    raw_df = results["raw_df"]
    valid_invoices_df = results["valid_invoices_df"]
    skipped_df = results["skipped_df"]
    reminder_df = results["reminder_df"]
    eligible_df = results["eligible_df"]
    classification_df = results["classification_df"]
    final_actions_df = results["final_actions_df"]
    output_dir = results["output_dir"]
    customer_replies_count = st.session_state.get("customer_replies_count", 0)

    st.markdown("---")
    st.subheader("3. Processing Summary")

    total_records = len(raw_df)
    valid_records = len(valid_invoices_df)
    skipped_records = len(skipped_df)
    eligible_records = len(eligible_df)

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Total Records", total_records)
    col2.metric("Valid Invoices", valid_records)
    col3.metric("Skipped Records", skipped_records)
    col4.metric("Eligible Reminders", eligible_records)
    col5.metric("Sample Replies", customer_replies_count)

    if save_to_output:
        st.success(f"CSV output files saved to: `{output_dir}`")

    # ---------------------------------------------------------------
    # Action Summary
    # ---------------------------------------------------------------

    st.subheader("4. Final Action Summary")

    if not final_actions_df.empty and "final_action" in final_actions_df.columns:
        action_counts = final_actions_df["final_action"].value_counts().reset_index()
        action_counts.columns = ["final_action", "count"]

        col1, col2 = st.columns([1, 2])

        with col1:
            st.dataframe(action_counts, use_container_width=True)

        with col2:
            st.bar_chart(
                action_counts.set_index("final_action")
            )
    else:
        st.warning("No final action records found.")

    # ---------------------------------------------------------------
    # Tabs for Outputs
    # ---------------------------------------------------------------

    st.subheader("5. Output Tables")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Reminder Eligibility",
        "Response Classification",
        "Final Actions",
        "Skipped Records"
    ])

    with tab1:
        st.markdown("### Reminder Eligibility")
        st.dataframe(reminder_df, use_container_width=True)

        st.download_button(
            label="Download reminder_eligibility.csv",
            data=convert_df_to_csv(reminder_df),
            file_name="reminder_eligibility.csv",
            mime="text/csv"
        )

    with tab2:
        st.markdown("### Response Classification")
        st.dataframe(classification_df, use_container_width=True)

        st.download_button(
            label="Download response_classification.csv",
            data=convert_df_to_csv(classification_df),
            file_name="response_classification.csv",
            mime="text/csv"
        )

    with tab3:
        st.markdown("### Final Actions")
        st.dataframe(final_actions_df, use_container_width=True)

        st.download_button(
            label="Download final_actions.csv",
            data=convert_df_to_csv(final_actions_df),
            file_name="final_actions.csv",
            mime="text/csv"
        )

    with tab4:
        st.markdown("### Skipped Records")

        if skipped_df.empty:
            st.success("No skipped records.")
        else:
            st.dataframe(skipped_df, use_container_width=True)

            st.download_button(
                label="Download skipped_records.csv",
                data=convert_df_to_csv(skipped_df),
                file_name="skipped_records.csv",
                mime="text/csv"
            )

    # ---------------------------------------------------------------
    # Email Preview Section
    # ---------------------------------------------------------------

    st.markdown("---")
    st.subheader("6. Generated Email Preview")

    if final_actions_df.empty:
        st.info("No generated email data found.")
    else:
        email_rows = final_actions_df[
            final_actions_df["should_generate_email"] == True
        ]

        if email_rows.empty:
            st.info("No emails need to be generated.")
        else:
            invoice_options = email_rows["document_number"].tolist()

            selected_invoice = st.selectbox(
                "Select invoice to preview email",
                invoice_options
            )

            selected_row = email_rows[
                email_rows["document_number"] == selected_invoice
            ].iloc[0]

            st.markdown("#### Email Details")

            detail_col1, detail_col2 = st.columns(2)

            with detail_col1:
                st.text_input(
                    "To",
                    value=selected_row["customer_email"],
                    disabled=True
                )

                st.text_input(
                    "Subject",
                    value=selected_row["email_subject"],
                    disabled=True
                )

            with detail_col2:
                st.text_input(
                    "Final Action",
                    value=selected_row["final_action"],
                    disabled=True
                )

                st.text_input(
                    "Reminder Stage",
                    value=selected_row["reminder_stage_label"],
                    disabled=True
                )

            st.text_area(
                "Email Body",
                value=selected_row["email_body"],
                height=280
            )

            st.info(
                "This app does not send real emails. Copy the generated email and send it manually."
            )