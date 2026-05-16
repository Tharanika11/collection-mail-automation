import json
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from ..services.workflow_service import run_collection_workflow


router = APIRouter()


@router.get("/")
def health_check() -> dict[str, str]:
    return {"message": "Collections Email Automation API is running"}


@router.post("/run-workflow")
async def run_workflow_endpoint(
    excel_file: UploadFile = File(...),
    replies_file: UploadFile | None = File(None),
) -> dict[str, Any]:
    """
    Required:
    - excel_file: AR transaction Excel file

    Optional:
    - replies_file: JSON list of customer replies

    If no replies_file is uploaded, all invoices are safely handled as no_reply.
    """

    try:
        raw_df = await read_excel_file(excel_file)
        customer_replies = await read_replies_file(replies_file)

        return run_collection_workflow(
            raw_df=raw_df,
            customer_replies=customer_replies,
        )

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Workflow failed: {str(error)}",
        ) from error


async def read_excel_file(excel_file: UploadFile) -> pd.DataFrame:
    content = await excel_file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded Excel file is empty.")

    try:
        df = pd.read_excel(BytesIO(content), engine="openpyxl")
        df.columns = [str(column).strip() for column in df.columns]
        return df

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail="Could not read Excel file. Please upload a valid .xlsx file.",
        ) from error


async def read_replies_file(
    replies_file: UploadFile | None,
) -> list[dict[str, Any]]:
    if replies_file is None:
        return []

    content = await replies_file.read()

    if not content:
        return []

    try:
        replies = json.loads(content.decode("utf-8"))

    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid replies JSON. Please upload a JSON array of reply objects.",
        ) from error

    if not isinstance(replies, list):
        raise HTTPException(
            status_code=400,
            detail="Replies JSON must contain a list of reply objects.",
        )

    return replies
