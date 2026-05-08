import os
import json
from datetime import datetime
from groq import Groq
from models import Claim
from dotenv import load_dotenv
load_dotenv()

CURRENT_YEAR = datetime.now().year
MAX_CLAIMS_PER_DOCUMENT = 5

SYSTEM_PROMPT = """You are a precise fact-extraction assistant.
Your job is to identify specific, verifiable claims from text.
Focus ONLY on claims that contain concrete, checkable information:
- Statistics and percentages (e.g. "sales grew by 47%")
- Dates and timelines (e.g. "founded in 1998")
- Financial figures (e.g. "revenue of $2.3 billion")
- Technical specifications (e.g. "processes 10,000 requests per second")
- Named rankings or positions (e.g. "largest company in the world")
- Scientific or research findings with numbers

Do NOT extract vague opinions, subjective statements, or general descriptions.
Extract at most 5 of the most important verifiable claims.

Respond ONLY with a valid JSON array. No explanation, no markdown.
Format:
[
  {"id": 1, "text": "exact claim here", "category": "statistic"},
  {"id": 2, "text": "another claim", "category": "date"}
]"""


def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")
    return Groq(api_key=api_key)


def identify_claims(pdf_text: str) -> list[Claim]:
    # Truncate to avoid token limits — first 6000 chars covers most docs
    truncated = pdf_text[:6000]

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract all verifiable claims from this text:\n\n{truncated}"}
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content or ""
    raw = raw.strip()

    # Strip markdown fences if model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    if not raw:
        raise ValueError("Groq returned an empty claim extraction response.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq returned invalid claim extraction JSON: {raw[:500]}") from e

    return [Claim(**item) for item in data[:MAX_CLAIMS_PER_DOCUMENT]]


def tag_future_claims(claims: list[Claim]) -> list[Claim]:
    """Mark claims about future years so verifier treats them as projections."""
    future_years = [str(year) for year in range(CURRENT_YEAR + 1, CURRENT_YEAR + 6)]

    for claim in claims:
        if any(year in claim.text for year in future_years):
            claim.category = "future_projection"

    return claims
