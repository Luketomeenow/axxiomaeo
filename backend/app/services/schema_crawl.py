"""Shared live-page JSON-LD check for schema validation.

Both validation paths (the Run-validation endpoint and the monthly worker)
used to fetch pages with a bare httpx client — default ``python-httpx`` UA, no
redirect following. The brand sites sit behind Cloudflare/WP Engine, which
bot-block that fingerprint from datacenter IPs (Railway), so every check came
back "Missing JSON-LD" even though the pages verifiably carry schema — Schema
Health read 0% across the board. This module fetches like a browser and
distinguishes "page has no schema" from "we couldn't see the page", so
coverage numbers mean what they say and self-heal doesn't regenerate schema
for pages it merely failed to fetch.
"""
import re

import httpx

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Any <script … type="application/ld+json" …> regardless of quote style,
# attribute order, or casing.
_LDJSON_RE = re.compile(
    r"<script[^>]+type\s*=\s*[\"']application/ld\+json[\"']", re.IGNORECASE
)


def new_crawl_client() -> httpx.AsyncClient:
    """Client for crawling live brand pages: browser headers, redirects on."""
    return httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=30.0, follow_redirects=True)


async def check_page_jsonld(client: httpx.AsyncClient, url: str) -> tuple[str, str | None]:
    """Fetch ``url`` and report one of three states (never raises httpx errors
    for HTTP-level failures — only transport exceptions propagate):

    - ``("valid", None)`` — page loaded and contains a JSON-LD block
    - ``("missing", detail)`` — page loaded fine but has no JSON-LD (schema is
      genuinely absent; safe to trigger regeneration)
    - ``("unreachable", detail)`` — HTTP error / bot challenge; says nothing
      about whether schema exists, so callers must NOT regenerate from it
    """
    resp = await client.get(url)
    if resp.status_code >= 400:
        hint = (
            " (bot-blocked — Cloudflare/WP Engine challenge?)"
            if resp.status_code in (401, 403, 429)
            else ""
        )
        return "unreachable", f"HTTP {resp.status_code} fetching page{hint}"
    if _LDJSON_RE.search(resp.text):
        return "valid", None
    return "missing", f"Page loads (HTTP {resp.status_code}) but contains no application/ld+json block"
