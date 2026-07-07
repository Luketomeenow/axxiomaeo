#!/usr/bin/env python3
"""Close comments + pings on EXISTING published posts across all brands.

The publish code sets comment_status/ping_status on every NEW post, but
posts published before that change inherit each site's Discussion default —
and most sites default to open. This backfills the fix onto existing posts.

Dry-run by default (lists what would change, touches nothing). Pass --apply
to actually update. Respects the same WP_ALLOW_COMMENTS / WP_ALLOW_PINGS
settings as the publish path, so it never contradicts your configured policy.

    python scripts/lock_discussion.py            # preview
    python scripts/lock_discussion.py --apply     # execute
    python scripts/lock_discussion.py --apply --brand quality   # one brand
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
from app.services.wordpress_service import WordPressService


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually update posts (default: dry-run preview)")
    parser.add_argument("--brand", help="Limit to one brand id (default: all configured brands)")
    args = parser.parse_args()

    settings = get_settings()
    wp = WordPressService()
    want_comment = settings.wp_comment_status
    want_ping = settings.wp_ping_status
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== Lock discussion settings ({mode}) — target: comment={want_comment} ping={want_ping} ===\n")

    async with AsyncSessionLocal() as session:
        q = select(Brand)
        if args.brand:
            q = q.where(Brand.id == args.brand)
        brands = list((await session.execute(q)).scalars().all())

    total_changed = 0
    for brand in brands:
        if not settings.wp_publish_configured(brand.id):
            print(f"[skip] {brand.id}: no WP credentials")
            continue
        try:
            # Pull published posts directly (get_existing_pages drops the
            # status fields we need to compare against).
            posts = await wp._request(
                brand, "GET",
                "posts?status=publish&per_page=100&_fields=id,link,comment_status,ping_status",
            )
        except Exception as e:
            print(f"[FAIL] {brand.id}: {e}")
            continue
        if not isinstance(posts, list):
            print(f"[skip] {brand.id}: unexpected response")
            continue

        needs = [p for p in posts if p.get("comment_status") != want_comment or p.get("ping_status") != want_ping]
        print(f"{brand.id}: {len(posts)} published post(s), {len(needs)} need changing")
        for p in needs:
            print(f"    #{p['id']}  comment {p.get('comment_status')}->{want_comment}  ping {p.get('ping_status')}->{want_ping}  {p.get('link','')}")
            if args.apply:
                try:
                    await wp._request(
                        brand, "POST", f"posts/{p['id']}",
                        json={"comment_status": want_comment, "ping_status": want_ping},
                    )
                    total_changed += 1
                except Exception as e:
                    print(f"      [FAIL] {e}")

    print(f"\n{'Changed' if args.apply else 'Would change'}: {total_changed if args.apply else 'run with --apply to execute'}")
    if not args.apply:
        print("(dry-run — nothing was modified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
