"""Keep the phone number and call-to-action on published posts current.

Each post's CTA block (and any phone in its body) is baked into the HTML when
the post is generated, so changing a brand's phone in Brand Settings only
reaches posts written afterwards. In October 2026 four brands' posts all
carried a CallRail *website pool* number, copied from a live site where the
swap script had already replaced the main line. CallRail never swaps a pool
number back, so a call from a post was credited to whichever visitor last held
that number, and the posts' calls landed on the wrong pages.

refresh_cta_and_phone rebuilds a post's CTA with the brand's current phone and
contact page, and replaces the numbers that came from the old CTA (or that a
person names) everywhere else in the post. It never touches other numbers,
such as a regulator's phone quoted in the article. refresh_brand_posts runs it
over a brand's published posts from their stored HTML: a preview by default,
or WordPress updates in small batches when a person applies it.
"""

import logging
import re
from collections import Counter

from bs4 import BeautifulSoup
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece
from app.services.content_enrichment import ensure_cta_block, find_contact_url

logger = logging.getLogger(__name__)


def phone_digits(value: str | None) -> str | None:
    """The 10-digit US number in ``value`` (a leading country code 1 is
    dropped), or None when it isn't one."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def _number_pattern(d10: str) -> re.Pattern:
    """Any common way of writing the number: 8446469660, 844-646-9660,
    (844) 646-9660, 844.646.9660, +1 844 646 9660, 1-844-646-9660."""
    a, b, c = d10[:3], d10[3:6], d10[6:]
    return re.compile(rf"(?<!\d)(?:\+?1[\s.\-]?)?\(?{a}\)?[\s.\-]?{b}[\s.\-]?{c}(?!\d)")


def cta_numbers(html: str) -> set[str]:
    """10-digit numbers in the post's CTA call links."""
    soup = BeautifulSoup(html or "", "lxml")
    found = set()
    for block in soup.select(".aeo-cta"):
        for a in block.select('a[href^="tel:"]'):
            if d := phone_digits(a.get("href", "")[4:]):
                found.add(d)
    return found


def refresh_cta_and_phone(
    html: str,
    brand: Brand,
    contact_url: str | None,
    old_numbers: set[str] | None = None,
) -> tuple[str, set[str]]:
    """Return (new_html, numbers_replaced). Unchanged input when the CTA is
    already current and no old number appears."""
    if not html:
        return html, set()
    current = phone_digits(brand.phone)
    replace = {d for d in (old_numbers or set()) | cta_numbers(html) if d and d != current}

    soup = BeautifulSoup(html, "lxml")
    blocks = soup.select(".aeo-cta")
    out = html
    if blocks:
        for block in blocks:
            block.decompose()
        out = str(soup)
    out = ensure_cta_block(out, brand, contact_url)

    replaced = set()
    display = (brand.phone or "").strip() if current else ""
    for d10 in replace:
        pattern = _number_pattern(d10)
        if not pattern.search(out):
            continue
        replaced.add(d10)
        if current:
            out = re.sub(r"tel:" + pattern.pattern, f"tel:{current}", out)
            out = pattern.sub(display, out)
        else:
            # No phone to point at: drop the link, keep the surrounding words.
            out = re.sub(rf'<a[^>]*href="tel:{pattern.pattern}"[^>]*>(.*?)</a>', r"\1", out)
            out = pattern.sub("", out)

    # Re-serialising an untouched document can still reorder attributes; only
    # report a change when the CTA or a number really changed.
    if not replaced and _cta_signature(out) == _cta_signature(html):
        return html, set()
    return out, replaced


def _cta_signature(html: str) -> tuple:
    soup = BeautifulSoup(html or "", "lxml")
    return tuple(
        (a.get("class") and a.get("class")[0], a.get("href"), a.get_text(" ", strip=True))
        for block in soup.select(".aeo-cta")
        for a in block.select("a")
    )


async def _latest_draft(db: AsyncSession, brand_id: str, slug: str | None) -> ContentDraft | None:
    if not slug:
        return None
    return (
        await db.execute(
            select(ContentDraft)
            .where(
                ContentDraft.brand_id == brand_id,
                ContentDraft.slug == slug,
                ContentDraft.html_content.is_not(None),
            )
            .order_by(ContentDraft.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def refresh_brand_posts(
    db: AsyncSession,
    brand: Brand,
    *,
    apply: bool = False,
    limit: int = 20,
    old_numbers: list[str] | None = None,
) -> dict:
    """Preview (default) or apply the CTA/phone refresh for one brand.

    Apply updates at most ``limit`` posts per call, so each request stays
    well inside the gateway timeout. The refresh is idempotent: updated posts
    drop out of the next preview, so the dashboard calls again until
    ``remaining`` is 0.
    """
    from app.services.content_service import _inject_brand_phone
    from app.services.schema_service import build_combined_schema
    from app.services.wordpress_service import WordPressService

    wp = WordPressService()
    pages = await wp.get_existing_pages(brand, post_type="pages")
    contact_url = find_contact_url(pages)
    extra = {d for d in (phone_digits(n) for n in (old_numbers or [])) if d}

    pieces = (
        await db.execute(
            select(ContentPiece)
            .where(
                ContentPiece.brand_id == brand.id,
                ContentPiece.status == "published",
                ContentPiece.wp_post_id.is_not(None),
            )
            .order_by(ContentPiece.published_at.desc())
        )
    ).scalars().all()

    found = Counter()
    pending, samples, errors = [], [], []
    no_html = 0
    for piece in pieces:
        draft = await _latest_draft(db, brand.id, piece.slug)
        if not draft or not draft.html_content:
            no_html += 1
            continue
        original = _inject_brand_phone(draft.html_content, brand.phone)
        refreshed, replaced = refresh_cta_and_phone(original, brand, contact_url, extra)
        if refreshed == original:
            continue
        found.update(replaced)
        pending.append((piece, draft, refreshed))
        if len(samples) < 5:
            samples.append(
                {"title": piece.title, "url": piece.wp_post_url, "replaced": sorted(replaced)}
            )

    updated = 0
    if apply:
        for piece, draft, refreshed in pending[: max(1, limit)]:
            try:
                schema_json, _ = build_combined_schema(
                    refreshed, brand, piece.title or "", piece.content_type or "faq_hub"
                )
                await wp.update_post(
                    brand, piece.wp_post_id, content=refreshed, schema_json=schema_json, post_type="posts"
                )
                draft.html_content = refreshed
                # Commit per post: if the request is cut off mid-batch, the
                # posts already updated on WordPress stay recorded as done.
                await db.commit()
                updated += 1
            except Exception as exc:  # one bad post must not stop the batch
                logger.warning("CTA refresh failed for %s post %s: %s", brand.id, piece.wp_post_id, exc)
                errors.append({"title": piece.title, "error": str(exc)[:200]})

    return {
        "brand_id": brand.id,
        "phone": brand.phone,
        "contact_url": contact_url,
        "published_posts": len(pieces),
        "posts_to_update": len(pending),
        "posts_without_stored_html": no_html,
        "old_numbers": dict(found),
        "samples": samples,
        "applied": apply,
        "updated": updated,
        "remaining": max(0, len(pending) - updated),
        "errors": errors,
    }


_TRACKER_SQL = text(r"""
SELECT coalesce(tracking_number_name, '') AS tracker,
       coalesce(company_name, '') AS company,
       count(DISTINCT call_id) AS calls
FROM public.fact_callrail_call
WHERE right(regexp_replace(coalesce(tracking_number, ''), '\D', '', 'g'), 10) = :digits
  AND start_time > now() - interval '180 days'
GROUP BY 1, 2
ORDER BY 3 DESC
""")


async def phone_check(db: AsyncSession, phone: str | None) -> dict:
    """Is ``phone`` one of CallRail's rotating website numbers? Reads the
    marketing warehouse (calls by tracking number, last 180 days). A website
    pool number in a post's CTA is never swapped per visitor, so calls to it
    land on the wrong page."""
    digits = phone_digits(phone)
    if not digits:
        return {"checked": False, "reason": "not a 10-digit US number"}
    try:
        async with db.begin_nested():
            rows = (await db.execute(_TRACKER_SQL, {"digits": digits})).all()
    except Exception:
        logger.warning("Phone check: CallRail warehouse unavailable", exc_info=True)
        return {"checked": False, "reason": "CallRail data unavailable"}
    trackers = [{"tracker": r.tracker, "company": r.company, "calls": r.calls} for r in rows]
    pool = [t for t in trackers if re.search(r"website|pool|dynamic|visitor", t["tracker"], re.I)]
    return {
        "checked": True,
        "tracking_number": bool(trackers),
        "website_pool": bool(pool),
        "trackers": trackers[:5],
    }
