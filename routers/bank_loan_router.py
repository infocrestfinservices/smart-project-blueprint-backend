"""
bank_loan_router.py

HTTP surface for the Bank Loan report pipeline.

  POST /bank-loan/generate  -> Generic Pipeline -> (Bank Loan executor) -> .xlsx

The router validates the request and delegates to the Generic Pipeline. It no longer
knows anything about Bank Loan orchestration: it simply calls run_report_pipeline,
which resolves the PurposeConfig via the Purpose Catalog, selects the Bank Loan
executor, and delegates to the existing services/bank_loan_pipeline_service exactly as
before. No AI, template, Excel, orchestration or file-writing logic here.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.generic_pipeline_service import run_report_pipeline

logger = logging.getLogger("bank_loan")

router = APIRouter(prefix="/bank-loan", tags=["Bank Loan"])


class BankLoanRequest(BaseModel):
    industry: str = Field(..., min_length=1, description="e.g. 'Manufacturing'")
    purpose: str = Field("Bank Loan", min_length=1)
    user_details: str = Field(..., min_length=1,
                              description="Free-form description of the business and the facility sought")


@router.post("/generate")
def generate_bank_loan_report(req: BankLoanRequest):
    """Generate a complete, recalculated Bank Loan workbook and return the
    pipeline's result dict verbatim.

    Delegates to the Generic Pipeline, which routes 'Bank Loan' to the existing Bank
    Loan pipeline unchanged — so the response is byte-for-byte what it was before."""
    try:
        return run_report_pipeline(
            industry=req.industry,
            purpose=req.purpose,
            user_details=req.user_details,
        )
    except ValueError as e:
        # unparseable AI JSON, or the template is not registered
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("bank-loan generation failed")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")
