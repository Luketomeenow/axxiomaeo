import asyncio
import logging
import re
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs,
) -> Any:
    last_error = None
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            delay = base_delay * (2**attempt)
            logger.warning("Attempt %d failed: %s. Retrying in %.1fs", attempt + 1, e, delay)
            await asyncio.sleep(delay)
    raise last_error


def count_words(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html)
    return len(text.split())


def strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


BAD_OPENERS = [
    "great question",
    "it depends",
    "there are many factors",
    "that's a great",
    "excellent question",
    "well,",
    "in short,",
]


def check_direct_answer(first_100_words: str) -> tuple[bool, str]:
    lower = first_100_words.lower()
    for phrase in BAD_OPENERS:
        if phrase in lower[:80]:
            return False, f"Opens with weak phrase: '{phrase}'"
    return True, ""


def h2_question_ratio(html: str) -> tuple[float, int, int]:
    h2_pattern = re.compile(r"<h2[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
    h2s = h2_pattern.findall(html)
    if not h2s:
        return 0.0, 0, 0
    questions = sum(1 for h in h2s if h.strip().endswith("?"))
    return questions / len(h2s), questions, len(h2s)
