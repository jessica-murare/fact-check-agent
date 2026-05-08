import os
import json
import requests
import re
import time
from groq import Groq
from models import Claim, VerifiedClaim, Verdict
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"

VERIFY_SYSTEM_PROMPT = """You are a rigorous fact-checking assistant.
You will be given a claim and web search results about it.
Analyze whether the claim is accurate based on the evidence.

Respond ONLY with a valid JSON object. No explanation, no markdown.
Format:
{
  "verdict": "VERIFIED" | "INACCURATE" | "FALSE" | "UNVERIFIABLE",
  "reason": "brief explanation — cite the source domain that confirmed this",
  "correct_value": "the correct figure/date/stat if the claim is wrong, else null",
  "primary_source_index": 0,
  "confidence": 85
}

Confidence scoring rules:
- 90-100: Multiple strong official sources confirm/deny the claim
- 70-89: One clear source confirms/denies
- 50-69: Indirect or partial evidence found
- 20-49: Very little relevant evidence, mostly inferred
- 0-19: No evidence found, pure guess

Always return a number between 0 and 100.

IMPORTANT RULE: If the claim category is "future_projection", do NOT verdict it as VERIFIED or FALSE.
Always return UNVERIFIABLE with reason: "This is a future projection and cannot be verified as fact."

Verdict definitions:
- VERIFIED: claim matches current evidence
- INACCURATE: claim is outdated or slightly wrong — include the correct value
- FALSE: claim is clearly contradicted by evidence
- UNVERIFIABLE: no relevant evidence found either way"""


def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")
    return Groq(api_key=api_key)


def search_web(query: str, max_results: int = 2) -> list[dict]:
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


def build_search_query(claim: Claim) -> str:
    text = claim.text.lower()

    gov_keywords = [
        "budget", "ministry", "government", "scheme", "allocation",
        "crore", "lakh", "indiaai", "policy", "act", "parliament",
    ]
    if any(keyword in text for keyword in gov_keywords):
        return f"{claim.text} site:gov.in OR site:pib.gov.in OR site:indiaai.gov.in"

    pricing_keywords = ["price", "pricing", "plan", "subscription", "cost", "per month"]
    if any(keyword in text for keyword in pricing_keywords):
        return f"{claim.text} official pricing page 2024 2025"

    return f"{claim.text} fact check"


def is_pricing_claim(claim: Claim) -> bool:
    keywords = ["$", "price", "pricing", "plan", "per month", "subscription", "cost"]
    return any(keyword in claim.text.lower() for keyword in keywords)


def infer_product_name(claim: Claim) -> str:
    text = claim.text.strip()
    parts = re.split(
        r"\b(costs?|priced|pricing|prices?|plans?|subscription|starts? at|charges?)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    candidate = parts[0].strip(" .,:;\"'")
    candidate = re.sub(r"^(the|a|an)\s+", "", candidate, flags=re.IGNORECASE)

    if 2 <= len(candidate) <= 80:
        return candidate

    return " ".join(text.split()[:4])


def find_pricing_page_url(product_name: str) -> str:
    domain_hint = re.sub(r"[^a-z0-9]", "", product_name.lower())
    query = f"{product_name} pricing official site:{domain_hint}.com"
    results = search_web(query, max_results=2)

    for result in results:
        url = result.get("href", "")
        if "pricing" in url.lower():
            return url

    return results[0].get("href", "") if results else ""


def fetch_page_text(url: str) -> str:
    if not url:
        return ""

    try:
        response = httpx.get(
            url,
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        return text[:2000]
    except Exception:
        return ""


def fetch_pricing_page(product_name: str) -> str:
    """Try to fetch the actual pricing page text for a SaaS product."""
    return fetch_page_text(find_pricing_page_url(product_name))


def verify_claim(claim: Claim) -> VerifiedClaim:
    search_query = build_search_query(claim)
    results = search_web(search_query)

    extra_context = ""
    if is_pricing_claim(claim):
        match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", claim.text)
        product = match.group(1) if match else claim.text.split()[0]
        page_text = fetch_pricing_page(product)
        if page_text:
            extra_context = f"\n\nDirect pricing page content:\n{page_text}"

    # Format snippets for the LLM
    if results:
        snippets = "\n\n".join([
            f"Source {index}: {r.get('href', 'unknown')}\n{r.get('title', '')}: {r.get('body', '')}"
            for index, r in enumerate(results)
        ])
        sources = [r.get("href", "") for r in results if r.get("href")]
    else:
        snippets = "No search results found."
        sources = []

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Claim: \"{claim.text}\"\n"
                f"Category: {claim.category}\n\n"
                f"Web search results:\n{snippets}"
                f"{extra_context}"
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

    source_index = result.get("primary_source_index", 0)
    try:
        source_index = int(source_index)
    except (TypeError, ValueError):
        source_index = 0

    if sources and 0 <= source_index < len(sources):
        primary_url = sources[source_index]
        reason_with_source = f"{result['reason']} — [source]({primary_url})"
    else:
        reason_with_source = result["reason"]

    try:
        confidence = int(result.get("confidence", 50))
    except (TypeError, ValueError):
        confidence = 50
    confidence = max(0, min(100, confidence))

    return VerifiedClaim(
        id=claim.id,
        text=claim.text,
        category=claim.category,
        verdict=Verdict(result["verdict"]),
        reason=reason_with_source,
        correct_value=result.get("correct_value"),
        sources=sources,
        confidence=confidence,
    )


def verify_all_claims(claims: list[Claim]) -> list[VerifiedClaim]:
    verified = []
    for claim in claims:
        verified.append(verify_claim(claim))
        time.sleep(1)
    return verified
