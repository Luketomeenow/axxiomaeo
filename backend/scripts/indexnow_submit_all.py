#!/usr/bin/env python3
"""Bulk-submit every published post URL on every brand site to IndexNow.

Run once after installing mu-plugin v1.2.0 (which serves the IndexNow key
file) to get the whole back-catalog into Bing's pipeline; new posts ping
automatically at publish time. Needs no database and no WP credentials — it
enumerates posts from each site's public REST API.

Per host it first verifies https://<host>/<key>.txt is live and matches; a
host without the key file is skipped with instructions (submitting would just
be rejected with 403).

    python scripts/indexnow_submit_all.py            # dry-run: show counts
    python scripts/indexnow_submit_all.py --apply    # actually submit
"""
import argparse
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.services.indexnow_service import submit_urls

SITES = [
    "https://axxiomelevatorfl.com",
    "https://ameritexelevator.com",
    "https://azelevatorsolutions.com",
    "https://liftechelevator.com",
    "https://qualityelevator.com",
    "https://carolinaelevatorservice.com",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (AxxiomAEO IndexNow submitter)"}


async def list_published_urls(client: httpx.AsyncClient, base: str) -> list[str]:
    urls: list[str] = []
    page = 1
    while True:
        resp = await client.get(
            f"{base}/wp-json/wp/v2/posts",
            params={"per_page": 100, "page": page, "status": "publish", "_fields": "link"},
        )
        if resp.status_code == 400:  # past the last page
            break
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        urls.extend(p["link"] for p in batch if p.get("link"))
        page += 1
    return urls


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Submit (default: dry-run)")
    args = parser.parse_args()

    key = get_settings().indexnow_key
    if not key:
        sys.exit("INDEXNOW_KEY is not configured")

    ready: list[str] = []
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
        for base in SITES:
            host = base.removeprefix("https://")
            try:
                resp = await client.get(f"{base}/{key}.txt")
                key_ok = resp.status_code == 200 and resp.text.strip() == key
            except Exception as e:
                print(f"[{host}] UNREACHABLE ({e}) — skipped")
                continue
            if not key_ok:
                print(f"[{host}] key file NOT live (HTTP {resp.status_code}) — "
                      "install mu-plugin v1.2.0 on this site first; skipped")
                continue

            try:
                urls = await list_published_urls(client, base)
            except Exception as e:
                print(f"[{host}] couldn't list posts: {e} — skipped")
                continue
            print(f"[{host}] key file OK · {len(urls)} published post URLs")
            ready.extend(urls)

        if not args.apply:
            print(f"\nDRY-RUN: would submit {len(ready)} URLs. Pass --apply to submit.")
            return 0

        results = await submit_urls(ready)
        print(f"\nSubmitted {len(ready)} URLs → {results}")
        return 0 if all(v == "ok" for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
