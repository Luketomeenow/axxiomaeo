import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class BingService:
    def __init__(self):
        self.api_key = get_settings().bing_api_key

    async def get_index_status(self, site_url: str) -> dict:
        if not self.api_key:
            return {"indexed_pages": 0, "status": "not_configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://ssl.bing.com/webmaster/api.svc/json/GetUrlInfo",
                    params={"siteUrl": site_url, "apikey": self.api_key},
                )
                if response.status_code == 200:
                    data = response.json()
                    return {"indexed_pages": data.get("d", {}).get("IndexedPages", 0), "status": "ok"}
        except Exception as e:
            logger.warning("Bing API error: %s", e)
        return {"indexed_pages": 0, "status": "error"}

    async def submit_url(self, site_url: str, url: str) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://ssl.bing.com/webmaster/api.svc/json/SubmitUrl",
                    params={"apikey": self.api_key},
                    json={"siteUrl": site_url, "url": url},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning("Bing submit error: %s", e)
            return False
