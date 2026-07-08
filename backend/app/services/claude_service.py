import re
import anthropic
from app.config import get_settings
from app.prompts.content_prompts import CORRECTION_PROMPT, build_prompt
from app.services.cost_service import create_and_record
from app.utils.helpers import check_direct_answer, h2_question_ratio, strip_html


class ClaudeService:
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or "sk-placeholder")
        self.model = settings.claude_model

    async def generate_content(
        self,
        content_type: str,
        brand_name: str,
        target_query: str,
        markets: list[str],
        title: str = "",
        city: str = "",
        state: str = "",
        vertical: str = "healthcare",
    ) -> str:
        prompt = build_prompt(
            content_type=content_type,
            brand_name=brand_name,
            target_query=target_query,
            markets=markets,
            title=title,
            city=city,
            state=state,
            vertical=vertical,
        )
        response = await create_and_record(
            self.client,
            operation="content_generation",
            model=self.model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        return self._clean_html(content)

    async def regenerate_with_correction(
        self,
        failure_reason: str,
        target_query: str,
        brand_name: str,
        previous_content: str,
    ) -> str:
        prompt = CORRECTION_PROMPT.format(
            failure_reason=failure_reason,
            target_query=target_query,
            brand_name=brand_name,
        )
        response = await create_and_record(
            self.client,
            operation="content_correction",
            model=self.model,
            max_tokens=8192,
            messages=[
                {"role": "user", "content": f"Previous content:\n{previous_content[:3000]}"},
                {"role": "assistant", "content": previous_content[:500]},
                {"role": "user", "content": prompt},
            ],
        )
        return self._clean_html(response.content[0].text)

    async def refresh_content(
        self,
        target_query: str,
        brand_name: str,
        content_type: str,
        previous_content: str,
    ) -> str:
        from app.prompts.content_prompts import REFRESH_CONTENT_PROMPT

        prompt = REFRESH_CONTENT_PROMPT.format(
            brand_name=brand_name,
            target_query=target_query,
            content_type=content_type,
        )
        response = await create_and_record(
            self.client,
            operation="content_refresh",
            model=self.model,
            max_tokens=8192,
            messages=[
                {"role": "user", "content": f"Existing page HTML:\n{previous_content[:6000]}"},
                {"role": "assistant", "content": "I have the existing page."},
                {"role": "user", "content": prompt},
            ],
        )
        return self._clean_html(response.content[0].text)

    def _clean_html(self, content: str) -> str:
        content = re.sub(r"^```html\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content)
        return content.strip()


async def validate_answer_first(
    content_html: str,
    original_query: str,
    content_type: str = "faq_hub",
) -> tuple[bool, str]:
    from app.prompts.content_prompts import CONTENT_TYPE_CONFIG
    from app.services.content_enrichment import count_faq_pairs, query_terms_in_text

    text = strip_html(content_html)
    words = text.split()
    first_100 = " ".join(words[:100])

    ok, reason = check_direct_answer(first_100)
    if not ok:
        return False, reason

    if not query_terms_in_text(original_query, first_100):
        return False, f"Opening does not address target query: {original_query}"

    ratio, questions, total = h2_question_ratio(content_html)
    if total > 0 and ratio < 0.6:
        return False, f"Only {questions}/{total} H2 tags are questions ({ratio:.0%}). Need 60%+."

    config = CONTENT_TYPE_CONFIG.get(content_type, CONTENT_TYPE_CONFIG["faq_hub"])
    min_words = max(200, int(config["min_words"] * 0.85))
    if len(words) < min_words:
        return False, f"Content too short: {len(words)} words (need ~{min_words}+)"

    min_faqs = config.get("num_faqs", 6)
    faq_count = count_faq_pairs(content_html)
    if faq_count < int(min_faqs * 0.75):
        return False, f"Only {faq_count} FAQ H2s found (need ~{min_faqs})"

    return True, ""
