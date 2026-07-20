"""Live verification of external links in generated HTML.

The prompt tells the model to link only to a short list of vetted authority
URLs, but a prompt is advice, not a guarantee — the model still invents deep
URLs on trusted domains (e.g. asme.org product pages that moved years ago),
and those 404 the moment a reader clicks them. This module is the enforcement
layer: every external href is probed against the live web before content
ships. A link that is definitively gone (404/410, dead domain, redirected to
nowhere) is swapped for a curated same-domain fallback when one verifies OK,
otherwise unwrapped so the words survive but the 404 doesn't. Links that can't
be verified (bot-blocked, transient errors) are kept — this gate must never
strip a working link.
"""
import asyncio
import logging
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_TIMEOUT = httpx.Timeout(8.0)
_MAX_CONCURRENT_PROBES = 5

# Statuses that mean "this page is gone" — vs. bot-blocking (401/403/429) or
# transient server trouble (5xx), which must not cost a working link its href.
_GONE_STATUSES = {404, 410}
# Error messages that identify a DNS failure — a domain that doesn't resolve
# is an invented link, not a flaky one.
_DNS_FAILURE_MARKERS = ("getaddrinfo", "name or service not known", "nodename nor servname")
# Path fragments of the "we redirected you to our error page" pattern.
_SOFT_404_HINTS = ("404", "not-found", "page-not-found", "pagenotfound")

# Curated safe landing page per authority domain — where a dead deep link is
# re-pointed instead of being dropped, preserving the outbound citation. Each
# fallback is itself verified live before being swapped in.
_DOMAIN_FALLBACKS = {
    "asme.org": "https://www.asme.org/codes-standards",
    "ada.gov": "https://www.ada.gov/",
    "osha.gov": "https://www.osha.gov/",
}

# url -> (verdict, expires_at). Confirmed verdicts are stable; "unknown" gets a
# short TTL so a transient failure doesn't stick for a whole backfill run.
_verdict_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL_OK = 15 * 60.0
_CACHE_TTL_UNKNOWN = 60.0


def _norm_host(netloc: str) -> str:
    return (netloc or "").lower().removeprefix("www.")


def _fallback_for(url: str) -> str | None:
    host = _norm_host(urlparse(url).netloc)
    for domain, fallback in _DOMAIN_FALLBACKS.items():
        if host == domain or host.endswith("." + domain):
            # Never "fall back" to the URL that just failed.
            return fallback if fallback.rstrip("/") != url.rstrip("/") else None
    parsed = urlparse(url)
    if parsed.path.strip("/") or parsed.query:
        return f"{parsed.scheme}://{parsed.netloc}/"
    return None


def _classify(original_url: str, resp: httpx.Response) -> str:
    if resp.status_code in _GONE_STATUSES:
        return "gone"
    if 200 <= resp.status_code < 400:
        orig_path = urlparse(original_url).path.strip("/").lower()
        final_path = (resp.url.path or "/").strip("/").lower()
        # Deep link answered by the homepage, or by an error page that returns
        # 200 — both are how sites say 404 without sending a 404.
        if orig_path and not final_path:
            return "gone"
        if any(h in final_path for h in _SOFT_404_HINTS) and not any(
            h in orig_path for h in _SOFT_404_HINTS
        ):
            return "gone"
        return "ok"
    return "unknown"


async def _probe(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.head(url)
        verdict = _classify(url, resp)
        if verdict != "unknown":
            return verdict
        # HEAD refused (403/405/501/...) — judge on a real GET, headers only.
        async with client.stream("GET", url) as get_resp:
            return _classify(url, get_resp)
    except httpx.ConnectError as exc:
        msg = str(exc).lower()
        if any(marker in msg for marker in _DNS_FAILURE_MARKERS):
            return "gone"
        return "unknown"
    except httpx.HTTPError:
        return "unknown"


async def _verdict(client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore) -> str:
    now = time.monotonic()
    cached = _verdict_cache.get(url)
    if cached and cached[1] > now:
        return cached[0]
    async with sem:
        verdict = await _probe(client, url)
    ttl = _CACHE_TTL_UNKNOWN if verdict == "unknown" else _CACHE_TTL_OK
    _verdict_cache[url] = (verdict, now + ttl)
    return verdict


def _external_url(href: str, skip_hosts: set[str]) -> str | None:
    parsed = urlparse(href)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if _norm_host(parsed.netloc) in skip_hosts:
        return None
    return href


async def verify_external_links(html: str, skip_hosts: set[str] | None = None) -> str:
    """Probe every external <a href> and neutralize the ones that are gone.

    Gone (hard 404/410, dead DNS, redirect-to-homepage/error-page) → the href
    is swapped for a verified curated fallback on the same domain, else the
    anchor is unwrapped (text kept, link dropped). Unverifiable (bot-blocked,
    timeout, 5xx) → kept as-is. ``skip_hosts`` (normalized, no www.) skips the
    brand's own site — internal links are validated elsewhere against real WP
    pages. Returns the input string untouched when nothing changed; never
    raises.
    """
    if not html or "<a" not in html.lower():
        return html
    try:
        return await _verify(html, {_norm_host(h) for h in (skip_hosts or set()) if h})
    except Exception:
        logger.exception("External link verification failed; leaving HTML unchanged")
        return html


async def _verify(html: str, skip_hosts: set[str]) -> str:
    soup = BeautifulSoup(html, "lxml")
    anchors = [
        (a, url)
        for a in soup.find_all("a")
        if (url := _external_url(a.get("href", ""), skip_hosts))
    ]
    if not anchors:
        return html

    urls = {url for _, url in anchors}
    sem = asyncio.Semaphore(_MAX_CONCURRENT_PROBES)
    async with httpx.AsyncClient(
        headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
    ) as client:
        verdicts = dict(
            zip(urls, await asyncio.gather(*(_verdict(client, u, sem) for u in urls)))
        )

        changed = False
        for a, url in anchors:
            if verdicts.get(url) != "gone":
                continue
            fallback = _fallback_for(url)
            if fallback and await _verdict(client, fallback, sem) == "ok":
                a["href"] = fallback
                logger.info("Dead external link re-pointed: %s -> %s", url, fallback)
            else:
                a.unwrap()
                logger.info("Dead external link removed (text kept): %s", url)
            changed = True

    return str(soup) if changed else html
