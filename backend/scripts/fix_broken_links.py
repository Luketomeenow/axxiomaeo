#!/usr/bin/env python3
"""Content-hygiene backfill for ALREADY-published blog posts across brands:
broken/invented links AND the author-byline compliance fix.

Re-runs the link sanitizer over each published post's stored generated HTML —
converting stray markdown links, trimming malformed hrefs (the "…/]" 404s), and
unwrapping internal links to pages that don't exist — then probes every
EXTERNAL link against the live web (dead ones are re-pointed to a curated
fallback or unwrapped; e.g. invented asme.org deep links) and re-publishes the
cleaned HTML to WordPress. Internal links are validated against each brand's
real published posts/pages (fetched live from WP).

Re-publishes the stored generated HTML, so any manual edits made directly in
WordPress would be overwritten (these are auto-generated posts, so that's
normally what you want). Posts with no stored draft HTML are skipped and listed.

Dry-run by default (reports what would change, writes nothing). Pass --apply.

    python scripts/fix_broken_links.py                   # preview all brands
    python scripts/fix_broken_links.py --apply            # execute
    python scripts/fix_broken_links.py --brand quality    # one brand
    python scripts/fix_broken_links.py --apply --brand quality
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece
from app.services.content_enrichment import _brand_host, normalize_author_byline, sanitize_links
from app.services.content_service import _inject_brand_phone, _known_paths
from app.services.link_verification import verify_external_links
from app.services.schema_service import build_combined_schema
from app.services.wordpress_service import WordPressService

# Surface link_verification's INFO lines (which URL died, what replaced it).
logging.basicConfig(level=logging.WARNING, format="        %(message)s")
logging.getLogger("app.services.link_verification").setLevel(logging.INFO)


async def _update_healing_stale_id(wp, brand, piece, cleaned: str, schema_json: str = "") -> str:
    """Update the WP post; when the stored wp_post_id is stale (WP answers
    404 "Invalid post ID" because the post was deleted/recreated on the WP
    side), re-resolve the live id by slug, persist it on the piece, and retry.
    Returns "ok", "healed", or "missing" (slug gone from WP entirely)."""
    try:
        await wp.update_post(brand, piece.wp_post_id, content=cleaned, schema_json=schema_json, post_type="posts")
        return "ok"
    except ValueError as e:
        if "invalid post id" not in str(e).lower():
            raise
    live = await wp.find_by_slug(brand, piece.slug, post_type="posts")
    if not live:
        return "missing"
    piece.wp_post_id = live["id"]
    piece.wp_post_url = live["url"]
    await wp.update_post(brand, live["id"], content=cleaned, schema_json=schema_json, post_type="posts")
    return "healed"


async def _latest_draft_html(session, brand_id: str, slug: str | None) -> ContentDraft | None:
    if not slug:
        return None
    result = await session.execute(
        select(ContentDraft)
        .where(
            ContentDraft.brand_id == brand_id,
            ContentDraft.slug == slug,
            ContentDraft.html_content.isnot(None),
        )
        .order_by(ContentDraft.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument("--brand", help="Limit to one brand id (default: all)")
    args = parser.parse_args()

    wp = WordPressService()
    scanned = changed = skipped = failed = healed = missing = 0

    async with AsyncSessionLocal() as session:
        brands_q = select(Brand).order_by(Brand.id)
        if args.brand:
            brands_q = brands_q.where(Brand.id == args.brand)
        brands = list((await session.execute(brands_q)).scalars().all())

        for brand in brands:
            if not wp.settings.wp_publish_configured(brand.id):
                print(f"[{brand.id}] skipped — WordPress not configured")
                continue

            known = _known_paths(
                await wp.get_existing_pages(brand, post_type="posts")
                + await wp.get_existing_pages(brand, post_type="pages")
            )

            pieces = list(
                (
                    await session.execute(
                        select(ContentPiece).where(
                            ContentPiece.brand_id == brand.id,
                            ContentPiece.status == "published",
                            ContentPiece.wp_post_id.isnot(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            print(f"[{brand.id}] {len(pieces)} published posts, {len(known)} known internal paths")

            for piece in pieces:
                scanned += 1
                draft = await _latest_draft_html(session, brand.id, piece.slug)
                if not draft or not draft.html_content:
                    skipped += 1
                    print(f"  SKIP  {piece.slug} — no stored HTML (regenerate to fix)")
                    continue

                original = _inject_brand_phone(draft.html_content, brand.phone)
                cleaned = sanitize_links(original, brand, known)
                cleaned = await verify_external_links(cleaned, skip_hosts={_brand_host(brand)})
                # Compliance: swap the old individual-credential byline for the
                # team byline (idempotent — unchanged when already safe).
                cleaned = normalize_author_byline(cleaned, brand)
                if cleaned == original:
                    continue

                changed += 1
                before, after = original.count("<a "), cleaned.count("<a ")
                print(f"  FIX   {piece.slug} — anchors {before}->{after}  {piece.wp_post_url or ''}")
                if args.apply:
                    try:
                        # Refresh the post's schema meta alongside the content —
                        # the old schema asserted a Person author with an
                        # unattested certification jobTitle.
                        schema_json, _ = build_combined_schema(
                            cleaned, brand, piece.title or "", piece.content_type or "faq_hub"
                        )
                        outcome = await _update_healing_stale_id(wp, brand, piece, cleaned, schema_json)
                        if outcome == "missing":
                            missing += 1
                            print(f"        ! slug not on WordPress anymore — stored post id {piece.wp_post_id} is an orphan")
                            continue
                        if outcome == "healed":
                            healed += 1
                            print(f"        ~ stale post id healed by slug -> {piece.wp_post_id}")
                        draft.html_content = cleaned
                        await session.commit()
                    except Exception as e:  # keep going; one bad post shouldn't stop the sweep
                        failed += 1
                        print(f"        ! WordPress update failed: {e}")

    mode = "APPLIED" if args.apply else "DRY-RUN (nothing written — pass --apply to execute)"
    print(f"\n{mode}: scanned {scanned}, {'fixed' if args.apply else 'would fix'} {changed}, "
          f"skipped {skipped}, failed {failed}, stale ids healed {healed}, missing on WP {missing}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
