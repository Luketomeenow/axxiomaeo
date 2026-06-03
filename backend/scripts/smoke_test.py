#!/usr/bin/env python3
"""Smoke-test the AEO API after DATABASE_URL is configured."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import jwt
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.database import check_db_connection, init_db
from app.utils.seed import seed_brands_and_queue


def make_test_token() -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": "smoke-test",
            "email": "smoke@test.local",
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )


async def main() -> int:
    settings = get_settings()
    if "YOUR_DB_PASSWORD" in settings.database_url or settings.database_url.endswith("@localhost"):
        print("ERROR: Set DATABASE_URL in backend/.env with your Supabase database password.")
        return 1

    print("Checking database connection...")
    try:
        await check_db_connection()
    except Exception as exc:
        print(f"ERROR: Database unreachable: {exc}")
        return 1

    print("Initializing schema and seed...")
    await init_db()
    await seed_brands_and_queue()

    token = make_test_token()
    headers = {"Authorization": f"Bearer {token}"}
    base = "http://127.0.0.1:8000"

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as client:
        health = await client.get("/health")
        print(f"GET /health -> {health.status_code} {health.json()}")

        for path in ("/api/brands", "/api/content/queue", "/api/reports/dashboard", "/api/notifications"):
            resp = await client.get(path)
            print(f"GET {path} -> {resp.status_code}")
            if resp.status_code != 200:
                print(resp.text[:500])
                return 1

    print("All smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
