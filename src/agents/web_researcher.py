"""Web Researcher - Investigates external websites based on email context.

Analyzes emails and researches relevant external sources:
- Government websites (gov.il, btl.gov.il, etc.)
- Bank portals
- Service providers
- Forms and deadlines

ADR-014 Phase 2: Web Research Capability
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    """Result from web research."""

    source_url: str
    source_name: str
    relevant_info: str
    forms_found: list[str]
    deadlines_found: list[str]
    action_required: str | None
    direct_links: list[str]


# Known Israeli government and service domains
KNOWN_SOURCES = {
    "ביטוח לאומי": {
        "domain": "btl.gov.il",
        "base_url": "https://www.btl.gov.il",
        "search_url": "https://www.btl.gov.il/search",
        "common_forms": [
            ("תביעה לדמי אבטלה", "https://www.btl.gov.il/טפסים/דמי%20אבטלה"),
            ("תביעה לקצבת ילדים", "https://www.btl.gov.il/טפסים/קצבת%20ילדים"),
            ("דיווח על שינוי כתובת", "https://www.btl.gov.il/טפסים/שינוי%20כתובת"),
        ],
    },
    "מס הכנסה": {
        "domain": "taxes.gov.il",
        "base_url": "https://www.gov.il/he/departments/israel_tax_authority",
        "common_forms": [
            ("החזר מס", "https://www.gov.il/he/service/tax-refund-request"),
            ("דוח שנתי", "https://www.gov.il/he/service/annual-tax-report"),
        ],
    },
    "משרד הפנים": {
        "domain": "gov.il/interior",
        "base_url": "https://www.gov.il/he/departments/ministry_of_interior",
        "common_forms": [
            ("חידוש דרכון", "https://www.gov.il/he/service/biometric-passport-request"),
            ("תעודת זהות", "https://www.gov.il/he/service/id-card-request"),
            ("אישור תושב", "https://www.gov.il/he/service/residency-certificate"),
        ],
    },
    "עירייה": {
        "domain": "municipal",
        "base_url": None,  # Varies by city
        "common_forms": [
            ("ארנונה", "payment"),
            ("רישוי עסקים", "business-license"),
        ],
    },
    "בנק": {
        "domain": "bank",
        "base_url": None,
        "common_actions": [
            "צפייה בחשבון",
            "העברה בנקאית",
            "הגדרת הוראת קבע",
        ],
    },
}

# Patterns to identify email sources
SOURCE_PATTERNS = {
    r"btl\.gov\.il|ביטוח לאומי|bituach leumi": "ביטוח לאומי",
    r"taxes\.gov\.il|מס הכנסה|tax authority": "מס הכנסה",
    r"משרד הפנים|ministry.?of.?interior|piba\.gov\.il": "משרד הפנים",
    r"עירי|municipality|iriya": "עירייה",
    r"bank|בנק|leumi|hapoalim|discount|mizrahi": "בנק",
}


class WebResearcher:
    """Researches external websites based on email content.

    Uses WebFetch for actual web lookups and LLM for analysis.

    Example:
        researcher = WebResearcher()
        results = await researcher.research_email(email_item)
    """

    def __init__(
        self,
        litellm_url: str = "https://litellm-gateway-production-0339.up.railway.app",
    ):
        """Initialize WebResearcher.

        Args:
            litellm_url: URL of LiteLLM Gateway for AI analysis
        """
        self.litellm_url = litellm_url

    def _identify_source(self, email_text: str) -> str | None:
        """Identify the source organization from email text.

        Args:
            email_text: Combined email subject, sender, and body

        Returns:
            Source name if identified, None otherwise
        """
        text_lower = email_text.lower()

        for pattern, source_name in SOURCE_PATTERNS.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                return source_name

        return None

    def _get_source_info(self, source_name: str) -> dict | None:
        """Get known information about a source.

        Args:
            source_name: Name of the source organization

        Returns:
            Source info dict or None
        """
        return KNOWN_SOURCES.get(source_name)

    async def _fetch_webpage(self, url: str) -> str | None:
        """Fetch a webpage and extract text content.

        Args:
            url: URL to fetch

        Returns:
            Page text content or None on failure
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; EmailAgent/1.0)",
                        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
                    },
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    # Simple HTML to text extraction
                    text = response.text
                    # Remove scripts and styles
                    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
                    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
                    # Remove HTML tags
                    text = re.sub(r"<[^>]+>", " ", text)
                    # Clean whitespace
                    text = re.sub(r"\s+", " ", text).strip()
                    return text[:5000]  # Limit size

        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")

        return None

    async def _analyze_with_llm(
        self,
        email_text: str,
        source_name: str,
        webpage_content: str | None,
    ) -> dict:
        """Use LLM to analyze email and web content.

        Args:
            email_text: Email content
            source_name: Identified source
            webpage_content: Fetched webpage content (if any)

        Returns:
            Analysis dict with findings
        """
        from openai import AsyncOpenAI

        source_info = self._get_source_info(source_name) or {}

        prompt = f"""אתה עוזר שמנתח מיילים ממוסדות ומספק מידע רלוונטי.

## המייל שהתקבל
{email_text}

## מקור זוהה
{source_name}

## מידע ידוע על המקור
{json.dumps(source_info, ensure_ascii=False, indent=2)}

{f"## תוכן מאתר האינטרנט{chr(10)}{webpage_content[:2000]}" if webpage_content else ""}

## המשימה שלך
נתח את המייל והמידע, וספק:
1. מה בדיוק נדרש מהמקבל?
2. אילו טפסים/מסמכים צריך?
3. מה הדדליין (אם יש)?
4. קישורים ישירים לפעולות נדרשות
5. טיפים להתמודדות יעילה

## פורמט התשובה (JSON)
{{
  "what_required": "תיאור קצר של מה נדרש",
  "documents_needed": ["מסמך 1", "מסמך 2"],
  "deadline": "DD/MM/YYYY או null",
  "deadline_urgency": "urgent|soon|flexible|none",
  "direct_links": [
    {{"title": "שם הקישור", "url": "https://...", "purpose": "מה עושים שם"}}
  ],
  "step_by_step": [
    "שלב 1: ...",
    "שלב 2: ..."
  ],
  "tips": ["טיפ 1", "טיפ 2"],
  "estimated_time": "זמן משוער לטיפול"
}}

ענה רק ב-JSON."""

        try:
            client = AsyncOpenAI(base_url=self.litellm_url, api_key="dummy")

            response = await client.chat.completions.create(
                model="claude-sonnet",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1500,
            )

            content = response.choices[0].message.content

            # Clean markdown
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("\n", 1)[0]

            return json.loads(content.strip())

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {
                "what_required": "לא הצלחתי לנתח",
                "documents_needed": [],
                "deadline": None,
                "direct_links": [],
                "step_by_step": [],
                "tips": [],
            }

    async def research_email(
        self,
        subject: str,
        sender: str,
        snippet: str,
        body: str = "",
    ) -> ResearchResult | None:
        """Research an email and gather relevant information.

        Args:
            subject: Email subject
            sender: Email sender
            snippet: Email snippet/preview
            body: Full email body (optional)

        Returns:
            ResearchResult with findings, or None if not researchable
        """
        email_text = f"נושא: {subject}\nמאת: {sender}\nתוכן: {snippet} {body}"

        # Identify source
        source_name = self._identify_source(email_text)
        if not source_name:
            logger.info("No known source identified for email")
            return None

        logger.info(f"Identified source: {source_name}")

        # Get source info
        source_info = self._get_source_info(source_name)

        # Fetch webpage if we have a base URL
        webpage_content = None
        source_url = ""
        if source_info and source_info.get("base_url"):
            source_url = source_info["base_url"]
            webpage_content = await self._fetch_webpage(source_url)

        # Analyze with LLM
        analysis = await self._analyze_with_llm(email_text, source_name, webpage_content)

        # Build result
        direct_links = []
        for link in analysis.get("direct_links", []):
            if isinstance(link, dict):
                direct_links.append(link.get("url", ""))
            elif isinstance(link, str):
                direct_links.append(link)

        return ResearchResult(
            source_url=source_url,
            source_name=source_name,
            relevant_info=analysis.get("what_required", ""),
            forms_found=analysis.get("documents_needed", []),
            deadlines_found=[analysis.get("deadline")] if analysis.get("deadline") else [],
            action_required="\n".join(analysis.get("step_by_step", [])),
            direct_links=direct_links,
        )

    async def research_batch(
        self,
        emails: list[dict],
    ) -> dict[str, ResearchResult]:
        """Research multiple emails.

        Args:
            emails: List of email dicts with subject, sender, snippet

        Returns:
            Dict mapping email IDs to research results
        """
        results = {}

        for email in emails:
            email_id = email.get("id", "unknown")
            result = await self.research_email(
                subject=email.get("subject", ""),
                sender=email.get("from", ""),
                snippet=email.get("snippet", ""),
                body=email.get("body", ""),
            )

            if result:
                results[email_id] = result

        return results


async def main() -> None:
    """Test WebResearcher."""
    import asyncio

    logging.basicConfig(level=logging.INFO)

    researcher = WebResearcher()

    # Test with a sample bureaucracy email
    result = await researcher.research_email(
        subject="דרישה להשלמת מסמכים - ביטוח לאומי",
        sender="noreply@btl.gov.il",
        snippet="שלום, עליך להגיש את המסמכים הבאים עד 30/01/2026: אישור תושב, צילום ת.ז",
    )

    if result:
        print("\n=== Research Result ===")
        print(f"Source: {result.source_name}")
        print(f"URL: {result.source_url}")
        print(f"Required: {result.relevant_info}")
        print(f"Forms: {result.forms_found}")
        print(f"Deadlines: {result.deadlines_found}")
        print(f"Actions:\n{result.action_required}")
        print(f"Links: {result.direct_links}")
    else:
        print("No research results")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
