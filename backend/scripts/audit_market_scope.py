#!/usr/bin/env python3
"""Find ALREADY-published posts that fail the market-scope guard — articles
about (or citing the regulators of) a state the brand doesn't operate in
(the 2026-09 cleanup found a Maryland AHJ post on the Florida brand and a
Cal/OSHA post on Arizona).

Read-only by default: prints one line per offending post with the brand,
WordPress post id, URL, and what tripped. Pass --unpublish to set those posts
back to draft on WordPress and return them to Content Review (the same
"Return to review" action the Published page offers), so a human decides
whether to regenerate or discard.

    python scripts/audit_market_scope.py                 # report, all brands
    python scripts/audit_market_scope.py --brand carolina
    python scripts/audit_market_scope.py --unpublish     # act on the report
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece
from app.services.content_service import ContentGenerationService
from app.utils.geography import validate_market_scope


async def main(brand_filter: str | None, unpublish: bool) -> int:
    settings = get_settings()
    offenders: list[tuple[ContentPiece, str]] = []
    async with AsyncSessionLocal() as session:
        brands = {b.id: b for b in (await session.execute(select(Brand))).scalars().all()}
        q = select(ContentPiece).where(ContentPiece.status == "published")
        if brand_filter:
            q = q.where(ContentPiece.brand_id == brand_filter)
        pieces = list((await session.execute(q.order_by(ContentPiece.brand_id, ContentPiece.id))).scalars().all())

        no_html = 0
        for piece in pieces:
            brand = brands.get(piece.brand_id)
            if not brand:
                continue
            draft = (
                await session.execute(
                    select(ContentDraft)
                    .where(
                        ContentDraft.brand_id == piece.brand_id,
                        ContentDraft.slug == piece.slug,
                        ContentDraft.html_content.isnot(None),
                    )
                    .order_by(ContentDraft.updated_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            html = draft.html_content if draft else ""
            if not html:
                no_html += 1
            ok, reason, _ = validate_market_scope(
                html,
                title=piece.title or "",
                target_query=piece.target_query or "",
                markets=brand.markets or [],
                brand_name=brand.name,
                max_body_mentions=max(0, settings.market_scope_max_foreign_mentions),
            )
            if not ok:
                offenders.append((piece, reason))

        print(f"Checked {len(pieces)} published post(s); {no_html} had no stored HTML (title/query only).")
        if not offenders:
            print("No out-of-market posts found.")
            return 0
        print(f"\n{len(offenders)} out-of-market post(s):\n")
        for piece, reason in offenders:
            print(f"  [{piece.brand_id}] piece {piece.id} wp:{piece.wp_post_id} {piece.wp_post_url}")
            print(f"      {piece.title}")
            print(f"      → {reason}\n")

        if not unpublish:
            print("Dry run. Re-run with --unpublish to set these to draft on WP and return them to review.")
            return 0

        svc = ContentGenerationService(session)
        done = failed = 0
        for piece, _ in offenders:
            try:
                result = await svc.return_to_review(piece.id, user_id="audit_market_scope")
                await session.commit()
                done += 1
                print(f"  unpublished piece {piece.id} ({piece.brand_id}) wp_set_to_draft={result['wp_set_to_draft']}")
            except Exception as e:  # keep going; report at the end
                failed += 1
                await session.rollback()
                print(f"  FAILED piece {piece.id} ({piece.brand_id}): {e}")
        print(f"\nReturned {done} to review, {failed} failed.")
        return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--brand", help="Only this brand id")
    parser.add_argument("--unpublish", action="store_true", help="Set offenders to WP draft + return to review")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.brand, args.unpublish)))
