import os
import json
import time
import requests
from groq import Groq
from models import Claim, VerifiedClaim, Verdict
from dotenv import load_dotenv
load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"

VERIFY_SYSTEM_PROMPT = """You are a rigorous fact-checking assistant.
You will be given a claim and web search results about it.
Analyze whether the claim is accurate based on the evidence.

Respond ONLY with a valid JSON object. No explanation, no markdown.
Format:
{
  "verdict": "VERIFIED" | "INACCURATE" | "FALSE" | "UNVERIFIABLE",
  "reason": "brief explanation of your verdict",
  "correct_value": "the correct figure/date/stat if the claim is wrong, else null"
}

Verdict definitions:
- VERIFIED: claim matches current evidence
- INACCURATE: claim is outdated or slightly wrong — include the correct value
- FALSE: claim is clearly contradicted by evidence
- UNVERIFIABLE: no relevant evidence found either way"""


def search_web(query: str, max_results: int = 4) -> list[dict]:
    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not set")

    try:
        response = requests.post(
            TAVILY_SEARCH_URL,
            headers={
                "Authorization": f"Bearer {TAVILY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "search_depth": "basic",
                "topic": "general",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        return [
            {
                "title": result.get("title", ""),
                "href": result.get("url", ""),
                "body": result.get("content", ""),
            }
            for result in data.get("results", [])
        ]
    except Exception:
        return []


def verify_claim(claim: Claim) -> VerifiedClaim:
    # Build a focused search query
    search_query = f"{claim.text} fact check"
    results = search_web(search_query)

    # Format snippets for the LLM
    if results:
        snippets = "\n\n".join([
            f"Source: {r.get('href', 'unknown')}\n{r.get('title', '')}: {r.get('body', '')}"
            for r in results
        ])
        sources = [r.get("href", "") for r in results if r.get("href")]
    else:
        snippets = "No search results found."
        sources = []

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Claim: \"{claim.text}\"\n"
                f"Category: {claim.category}\n\n"
                f"Web search results:\n{snippets}"
            )}
        ],
        temperature=0.1,
        max_tokens=500,
    )

    raw = response.choices[0].message.content or ""
    raw = raw.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    if not raw:
        raise ValueError(f"Groq returned an empty verification response for claim #{claim.id}.")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Groq returned invalid verification JSON for claim #{claim.id}: {raw[:500]}"
        ) from e

    return VerifiedClaim(
        id=claim.id,
        text=claim.text,
        category=claim.category,
        verdict=Verdict(result["verdict"]),
        reason=result["reason"],
        correct_value=result.get("correct_value"),
        sources=sources,
    )


def verify_all_claims(claims: list[Claim]) -> list[VerifiedClaim]:
    verified = []
    for claim in claims:
        result = verify_claim(claim)
        verified.append(result)
        time.sleep(1)  # respect Groq rate limits
    return verified
