import pandas as pd


REMINDER_STAGE_LABELS = {
    "initial": "Initial Reminder",
    "first": "1st Reminder",
    "second": "2nd Reminder",
    "third": "3rd Reminder",
    "escalation": "Escalation"
}


def assign_reminder_stage(aging_days: int) -> str | None:
    """
    Assigns reminder stage based on invoice aging days.
    """

    if aging_days == 4:
        return "initial"

    if aging_days == 6:
        return "first"

    if aging_days == 8:
        return "second"

    if aging_days == 10:
        return "third"

    if aging_days > 10:
        return "escalation"

    return None


def apply_reminder_rules(invoices_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds reminder eligibility and stage columns.
    """

    if invoices_df.empty:
        return invoices_df

    df = invoices_df.copy()

    df["reminder_stage"] = df["aging_days"].apply(assign_reminder_stage)
    df["reminder_stage_label"] = df["reminder_stage"].apply(
        lambda stage: REMINDER_STAGE_LABELS.get(stage, "Not Eligible")
    )
    df["is_eligible_for_reminder"] = df["reminder_stage"].notna()

    return df