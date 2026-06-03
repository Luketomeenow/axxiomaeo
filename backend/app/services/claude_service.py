import re
import anthropic
from app.config import get_settings
from app.prompts.content_prompts import CORRECTION_PROMPT, build_prompt
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
        response = await self.client.messages.create(
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
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            messages=[
                {"role": "user", "content": f"Previous content:\n{previous_content[:3000]}"},
                {"role": "assistant", "content": previous_content[:500]},
                {"role": "user", "content": prompt},
            ],
        )
        return self._clean_html(response.content[0].text)

    def _clean_html(self, content: str) -> str:
        content = re.sub(r"^```html\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content)
        return content.strip()


async def validate_answer_first(content_html: str, original_query: str) -> tuple[bool, str]:
    text = strip_html(content_html)
    words = text.split()
    first_100 = " ".join(words[:100])

    ok, reason = check_direct_answer(first_100)
    if not ok:
        return False, reason

    ratio, questions, total = h2_question_ratio(content_html)
    if total > 0 and ratio < 0.6:
        return False, f"Only {questions}/{total} H2 tags are questions ({ratio:.0%}). Need 60%+."

    if len(words) < 200:
        return False, f"Content too short: {len(words)} words"

    return True, ""
