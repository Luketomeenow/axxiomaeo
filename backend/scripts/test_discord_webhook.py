#!/usr/bin/env python3
"""Test DISCORD_WEBHOOK_URL by sending the latest published post per brand
through the real NotificationService._send_discord formatting.

Reads the webhook from settings (backend/.env) — never prints it. Fetches
each brand's most recent published post from its public WordPress API and
sends it exactly as an auto-publish "Published" notification would.

    python scripts/test_discord_webhook.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.config import get_settings
from app.services.notification_service import NotificationService

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
SITES = {
    "axxiom": "axxiomelevatorfl.com",
    "ameritex": "ameritexelevator.com",
    "arizona_es": "azelevatorsolutions.com",
    "liftech": "liftechelevator.com",
    "quality": "qualityelevator.com",
}


async def latest_post(domain: str) -> dict | None:
    url = f"https://{domain}/wp-json/wp/v2/posts?per_page=1&orderby=date&_fields=title,link"
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        r = await client.get(url, headers={"User-Agent": UA})
        rows = r.json() if r.status_code == 200 else []
    if isinstance(rows, list) and rows:
        return {"title": rows[0]["title"]["rendered"], "link": rows[0]["link"]}
    return None


async def main() -> int:
    settings = get_settings()
    if not settings.discord_webhook_url:
        print("DISCORD_WEBHOOK_URL not set in backend/.env — add it and re-run.")
        return 1

    # 1) Raw connectivity probe — surfaces the real HTTP status (the live
    #    _send_discord swallows errors, so we check the webhook directly first).
    async with httpx.AsyncClient(timeout=10.0) as client:
        probe = await client.post(
            settings.discord_webhook_url,
            json={"content": "**Axxiom AEO — webhook connectivity test**\nLatest published posts follow:"},
        )
    print(f"connectivity probe: HTTP {probe.status_code} ({'OK' if probe.status_code < 300 else 'FAILED'})")
    if probe.status_code >= 300:
        print("  Webhook rejected the request — check the URL is a valid, current Discord webhook.")
        return 1

    # 2) Send each brand's latest post through the REAL formatting code.
    class _NoDB:
        def add(self, *_a): ...
        async def flush(self): ...

    svc = NotificationService(_NoDB())
    sent = 0
    for brand, domain in SITES.items():
        post = await latest_post(domain)
        if not post:
            print(f"  [skip] {brand}: no published post found")
            continue
        # Mirror exactly what approve_and_publish passes to create():
        await svc._send_discord(f"Published: {post['title']}", post["link"])
        print(f"  [sent] {brand}: {post['title'][:50]}")
        sent += 1

    print(f"\nDone — probe + {sent} post message(s) sent. Check the Discord channel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
