import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from extractor import extract_text_from_pdf
from claim_identifier import identify_claims
from verifier import verify_all_claims
from models import AnalysisReport, Verdict

from dotenv import load_dotenv
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

app = FastAPI(title="Fact-Check Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "ok", "message": "Fact-Check Agent is running"}


@app.post("/analyze", response_model=AnalysisReport)
async def analyze_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()

    try:
        pdf_text = extract_text_from_pdf(contents)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    claims = identify_claims(pdf_text)

    if not claims:
        raise HTTPException(status_code=422, detail="No verifiable claims found in this PDF.")

    verified = verify_all_claims(claims)

    return AnalysisReport(
        filename=file.filename,
        total_claims=len(verified),
        verified_count=sum(1 for c in verified if c.verdict == Verdict.VERIFIED),
        inaccurate_count=sum(1 for c in verified if c.verdict == Verdict.INACCURATE),
        false_count=sum(1 for c in verified if c.verdict == Verdict.FALSE),
        unverifiable_count=sum(1 for c in verified if c.verdict == Verdict.UNVERIFIABLE),
        claims=verified,
    )