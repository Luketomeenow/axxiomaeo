"""IndexNow pings — tell Bing (and every IndexNow-participating engine) about
new/updated URLs the moment they publish.

Why this matters for AEO: ChatGPT search runs on Bing's index. A post Bing
hasn't crawled can't be cited, no matter how good it is. IndexNow needs no
account or API key — only a key file each site serves at /<key>.txt, which the
Axxiom AEO mu-plugin (v1.2.0+) provides. Failures here must never break a
publish: everything is fire-and-forget with logging.
"""

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.indexnow.org/indexnow"


def _group_by_host(urls: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for url in urls:
        host = urlparse(url).netloc
        if host:
            grouped.setdefault(host, []).append(url)
    return grouped


async def submit_urls(urls: list[str]) -> dict[str, str]:
    """Submit URLs to IndexNow, grouped per host (the key file is per-host).

    Returns {host: outcome} for logging/reporting. Never raises.
    """
    settings = get_settings()
    if not settings.indexnow_enabled or not settings.indexnow_key:
        return {}
    key = settings.indexnow_key
    results: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for host, host_urls in _group_by_host(urls).items():
            payload = {
                "host": host,
                "key": key,
                "keyLocation": f"https://{host}/{key}.txt",
                "urlList": host_urls[:10000],
            }
            try:
                resp = await client.post(_ENDPOINT, json=payload)
                # 200/202 = accepted; 403 = key file missing/mismatched on the
                # host (mu-plugin v1.2.0 not installed there yet); 422 = URLs
                # don't belong to the host.
                if resp.status_code in (200, 202):
                    results[host] = "ok"
                    logger.info("IndexNow: submitted %s url(s) for %s", len(host_urls), host)
                else:
                    results[host] = f"HTTP {resp.status_code}"
                    logger.warning(
                        "IndexNow rejected %s (%s): %s",
                        host, resp.status_code,
                        "key file missing on host?" if resp.status_code == 403 else resp.text[:120],
                    )
            except Exception as e:
                results[host] = f"error: {e}"
                logger.warning("IndexNow submit failed for %s: %s", host, e)
    return results


def submit_urls_background(urls: list[str]) -> None:
    """Fire-and-forget wrapper for use inside request/publish paths."""
    if not urls:
        return

    async def _run():
        try:
            await submit_urls(urls)
        except Exception:  # pragma: no cover — submit_urls already guards
            logger.exception("IndexNow background submit failed")

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:  # no running loop (sync caller) — skip quietly
        logger.debug("IndexNow: no event loop; skipped background submit")
