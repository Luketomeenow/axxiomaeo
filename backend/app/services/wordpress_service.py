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
        return {"Authorization": f"Basic {credentials}"}

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
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.request(method, url, headers=headers, **kwargs)
                    response.raise_for_status()
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
    ) -> dict:
        meta_fields = meta or {}
        if schema_json:
            meta_fields["aeo_schema_json"] = schema_json
        meta_fields["_aeo_last_updated"] = __import__("datetime").datetime.utcnow().isoformat()

        payload = {
            "title": title,
            "content": content,
            "slug": slug,
            "status": "publish",
            "meta": meta_fields,
        }
        result = await self._request(brand, "POST", post_type, json=payload)
        return {
            "post_id": result.get("id"),
            "post_url": result.get("link"),
            "brand_id": brand.id,
        }

    async def update_post(
        self,
        brand: Brand,
        post_id: int,
        content: str | None = None,
        schema_json: str = "",
        post_type: str = "posts",
    ) -> dict:
        payload: dict[str, Any] = {}
        if content:
            payload["content"] = content
        meta: dict[str, str] = {"_aeo_last_updated": __import__("datetime").datetime.utcnow().isoformat()}
        if schema_json:
            meta["aeo_schema_json"] = schema_json
        payload["meta"] = meta
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
