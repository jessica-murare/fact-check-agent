from pydantic import BaseModel
from typing import Optional
from enum import Enum


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    INACCURATE = "INACCURATE"
    FALSE = "FALSE"
    UNVERIFIABLE = "UNVERIFIABLE"


class Claim(BaseModel):
    id: int
    text: str                          # the exact claim from the PDF
    category: str                      # e.g. "statistic", "date", "financial figure"


class VerifiedClaim(BaseModel):
    id: int
    text: str
    category: str
    verdict: Verdict
    reason: str                        # explanation of verdict
    correct_value: Optional[str]       # what the real figure is, if wrong
    sources: list[str]                 # URLs used for verification


class AnalysisReport(BaseModel):
    filename: str
    total_claims: int
    verified_count: int
    inaccurate_count: int
    false_count: int
    unverifiable_count: int
    claims: list[VerifiedClaim]