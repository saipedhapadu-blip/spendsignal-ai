import os
import json
from typing import Optional
import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# AI enrichment is ONLY used when deterministic rules produce no result.
# AI must NOT invent facts. It must only summarize what is in the source text.

SYSTEM_PROMPT = """You are a commercial intelligence analyst for SpendSignal AI.
Your job is to analyze a regulatory filing, enforcement record, or government data excerpt
and identify whether the named organization may need to spend money on compliance,
remediation, cybersecurity, legal, audit, safety, quality, environmental, or risk-management solutions.

Rules:
- Only reference facts present in the provided text. Do not invent or infer beyond what is stated.
- Use neutral commercial language: 'may need', 'likely needs', 'potentially exposed to'.
- Do not accuse the organization of wrongdoing.
- Return ONLY a valid JSON object with these fields:
  - summary: 1-2 sentence neutral commercial summary (max 200 chars)
  - spend_categories: list of spend category strings (e.g. ["cybersecurity", "compliance_grc"])
  - sales_angle: 1 sentence suggested vendor outreach angle
  - confidence: one of low, medium, high
  - severity: one of low, medium, high, critical"""


async def enrich_trigger_with_ai(
    source_text: str,
    organization_name: str,
    source_type: str,
) -> Optional[dict]:
    """
    Use LLM to extract trigger intelligence from raw source text.
    Only called when deterministic rules return no triggers.
    Returns None if AI call fails or no key configured.
    """
    if not OPENAI_API_KEY:
        return None

    user_message = f"""Organization: {organization_name}
Source type: {source_type}

Source text excerpt:
{source_text[:3000]}

Analyze this text and return a JSON object per the system instructions."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OPENAI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 400,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            # Mark as AI-inferred (lower confidence in scoring)
            result["ai_inferred"] = True
            result["model"] = OPENAI_MODEL
            return result
    except Exception as e:
        return None


def enrich_trigger_sync(
    source_text: str,
    organization_name: str,
    source_type: str,
) -> Optional[dict]:
    """
    Synchronous wrapper for use in non-async contexts.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    enrich_trigger_with_ai(source_text, organization_name, source_type)
                )
                return future.result(timeout=35)
        else:
            return loop.run_until_complete(
                enrich_trigger_with_ai(source_text, organization_name, source_type)
            )
    except Exception:
        return None
