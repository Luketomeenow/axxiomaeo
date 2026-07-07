import asyncio
import base64
import logging
from typing import Any

import httpx
from slugify import slugify

from app.config import get_settings
from app.models.brand import Brand
from app.utils.helpers import retry_with_backoff

logger = logging.getLogger(__name__)

_brand_semaphores: dict[str, asyncio.Semaphore] = {}


def schema_carrier_meta() -> dict[str, str]:
    """Yoast noindex for thin schema carrier pages — JSON-LD still in source."""
    return {
        "_yoast_wpseo_meta-robots-noindex": "1",
        "_yoast_wpseo_meta-robots-nofollow": "0",
    }


def _get_semaphore(brand_id: str) -> asyncio.Semaphore:
    if brand_id not in _brand_semaphores:
        _brand_semaphores[brand_id] = asyncio.Semaphore(5)
    return _brand_semaphores[brand_id]


class WordPressService:
    def __init__(self):
        self.settings = get_settings()

    def _auth_header(self, brand: Brand) -> dict[str, str]:
        password = self.settings.get_wp_password(brand.id)
        username = self.settings.get_wp_username(brand.id)
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {
            "Authorization": f"Basic {credentials}",
            # WP Engine / Cloudflare may block POST without a browser-like UA.
            "User-Agent": f"WordPress/6.4; {brand.wp_url}",
        }

    def _base_url(self, brand: Brand) -> str:
        return brand.wp_url.rstrip("/") + "/wp-json/wp/v2"

    async def _request(
        self,
        brand: Brand,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict[str, Any]:
        async with _get_semaphore(brand.id):
            url = f"{self._base_url(brand)}/{endpoint.lstrip('/')}"
            headers = {**self._auth_header(brand), "Content-Type": "application/json"}

            async def do_request():
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                    response = await client.request(method, url, headers=headers, **kwargs)
                    if response.status_code >= 400:
                        detail = response.text[:300]
                        try:
                            wp_error = response.json()
                            if isinstance(wp_error, dict) and wp_error.get("message"):
                                detail = wp_error["message"]
                        except Exception:
                            pass
                        if response.status_code == 401:
                            raise ValueError(
                                f"WordPress login failed for {brand.id} — check WP_USERNAME_{brand.id.upper()} "
                                f"and WP_APP_PASSWORD_{brand.id.upper()} in backend .env, then restart the API."
                            )
                        if response.status_code == 403 and "<html" in response.text.lower():
                            raise ValueError(
                                f"WordPress blocked the API request for {brand.id} (403). "
                                "Check WP Engine / Cloudflare REST API access, or verify application password."
                            )
                        raise ValueError(f"WordPress API error {response.status_code} for {brand.id}: {detail}")
                    return response.json()

            return await retry_with_backoff(do_request)

    async def create_post(
        self,
        brand: Brand,
        title: str,
        content: str,
        slug: str,
        categories: list[str] | None = None,
        schema_json: str = "",
        meta: dict | None = None,
        post_type: str = "posts",
        noindex: bool = False,
        featured_media: int | None = None,
    ) -> dict:
        meta_fields = dict(meta or {})
        if noindex:
            meta_fields.update(schema_carrier_meta())
        if schema_json:
            meta_fields["aeo_schema_json"] = schema_json
        meta_fields["_aeo_last_updated"] = __import__("datetime").datetime.utcnow().isoformat()

        payload = {
            "title": title,
            "content": content,
            "slug": slug,
            "status": "publish",
            "meta": meta_fields,
            # Enforce our discussion policy regardless of the site's default —
            # keeps spam bots off unattended auto-published posts.
            "comment_status": self.settings.wp_comment_status,
            "ping_status": self.settings.wp_ping_status,
        }
        author_id = self.settings.get_wp_author_id(brand.id)
        if author_id:
            payload["author"] = author_id
        if featured_media:
            payload["featured_media"] = featured_media
        result = await self._request(brand, "POST", post_type, json=payload)
        return {
            "post_id": result.get("id"),
            "post_url": result.get("link"),
            "brand_id": brand.id,
        }

    async def upload_media(
        self,
        brand: Brand,
        image_bytes: bytes,
        filename: str,
        alt_text: str = "",
        caption: str = "",
        description: str = "",
    ) -> dict:
        """Upload image to WordPress media library."""
        url = f"{self._base_url(brand)}/media"
        headers = {
            **self._auth_header(brand),
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/png",
        }

        async with _get_semaphore(brand.id):

            async def do_upload():
                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                    response = await client.post(url, headers=headers, content=image_bytes)
                    if response.status_code >= 400:
                        detail = response.text[:300]
                        raise ValueError(f"WordPress media upload failed ({response.status_code}): {detail}")
                    return response.json()

            result = await retry_with_backoff(do_upload)

        media_id = result.get("id")
        source_url = result.get("source_url") or result.get("guid", {}).get("rendered", "")

        if media_id and (alt_text or caption or description):
            await self._request(
                brand,
                "POST",
                f"media/{media_id}",
                json={
                    "alt_text": alt_text,
                    "caption": caption,
                    "description": description or caption,
                },
            )

        return {"media_id": media_id, "source_url": source_url}

    async def update_post(
        self,
        brand: Brand,
        post_id: int,
        content: str | None = None,
        schema_json: str = "",
        post_type: str = "posts",
        featured_media: int | None = None,
    ) -> dict:
        payload: dict[str, Any] = {}
        if content:
            payload["content"] = content
        meta: dict[str, str] = {"_aeo_last_updated": __import__("datetime").datetime.utcnow().isoformat()}
        if schema_json:
            meta["aeo_schema_json"] = schema_json
        payload["meta"] = meta
        if featured_media:
            payload["featured_media"] = featured_media
        # Re-assert discussion policy on updates too, so a refresh/republish
        # can't silently revert a post to the site's open default.
        payload["comment_status"] = self.settings.wp_comment_status
        payload["ping_status"] = self.settings.wp_ping_status
        # Reassign on update too, so republishing an existing post moves it
        # from the API account to the brand's configured author.
        author_id = self.settings.get_wp_author_id(brand.id)
        if author_id:
            payload["author"] = author_id
        result = await self._request(brand, "POST", f"{post_type}/{post_id}", json=payload)
        return {"post_id": result.get("id"), "post_url": result.get("link"), "brand_id": brand.id}

    async def update_post_meta(
        self,
        brand: Brand,
        post_id: int,
        schema_json: str,
        post_type: str = "pages",
    ) -> dict:
        return await self.update_post(brand, post_id, schema_json=schema_json, post_type=post_type)

    async def set_post_status(
        self, brand: Brand, post_id: int, status: str, post_type: str = "posts"
    ) -> dict:
        """Change a post's status (e.g. 'draft' to unpublish, 'publish' to restore)."""
        result = await self._request(
            brand, "POST", f"{post_type}/{post_id}", json={"status": status}
        )
        return {
            "post_id": result.get("id"),
            "status": result.get("status"),
            "post_url": result.get("link"),
        }

    async def get_post_meta_schema(self, brand: Brand, post_id: int, post_type: str = "posts") -> str | None:
        try:
            result = await self._request(brand, "GET", f"{post_type}/{post_id}")
            meta = result.get("meta") or {}
            return meta.get("aeo_schema_json")
        except Exception as e:
            logger.warning("Failed to fetch schema meta for %s post %s: %s", brand.id, post_id, e)
            return None

    async def get_existing_pages(self, brand: Brand, post_type: str = "posts") -> list[dict]:
        try:
            result = await self._request(
                brand,
                "GET",
                f"{post_type}?status=publish&per_page=100",
            )
            if isinstance(result, list):
                return [
                    {"id": p["id"], "title": p["title"]["rendered"], "slug": p["slug"], "url": p["link"]}
                    for p in result
                ]
        except Exception as e:
            logger.warning("Failed to fetch pages for %s: %s", brand.id, e)
        return []

    async def find_by_slug(self, brand: Brand, slug: str, post_type: str = "posts") -> dict | None:
        try:
            result = await self._request(brand, "GET", f"{post_type}?slug={slug}")
            if isinstance(result, list) and result:
                p = result[0]
                return {"id": p["id"], "title": p["title"]["rendered"], "slug": p["slug"], "url": p["link"]}
        except Exception:
            pass
        return None

    @staticmethod
    def generate_slug(title: str, brand_name: str = "") -> str:
        clean = title
        if brand_name:
            clean = clean.replace(brand_name, "").strip()
        return slugify(clean, max_length=80)

    async def ping_bing_sitemap(self, brand: Brand) -> None:
        sitemap_url = f"{brand.wp_url.rstrip('/')}/sitemap_index.xml"
        ping_url = f"https://www.bing.com/ping?sitemap={sitemap_url}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(ping_url)
        except Exception as e:
            logger.warning("Bing sitemap ping failed for %s: %s", brand.id, e)
