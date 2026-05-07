import os
import json
from groq import Groq
from models import Claim
from dotenv import load_dotenv
load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

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

Respond ONLY with a valid JSON array. No explanation, no markdown.
Format:
[
  {"id": 1, "text": "exact claim here", "category": "statistic"},
  {"id": 2, "text": "another claim", "category": "date"}
]"""


def identify_claims(pdf_text: str) -> list[Claim]:
    # Truncate to avoid token limits — first 6000 chars covers most docs
    truncated = pdf_text[:6000]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract all verifiable claims from this text:\n\n{truncated}"}
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    return [Claim(**item) for item in data]