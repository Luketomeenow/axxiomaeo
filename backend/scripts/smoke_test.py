#!/usr/bin/env python3
"""Smoke-test the AEO API locally or against production."""

import argparse
import asyncio
import os
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
    secret = settings.supabase_jwt_secret
    if not secret:
        print("WARNING: SUPABASE_JWT_SECRET not set — API may reject auth in production mode")
        return ""
    return jwt.encode(
        {
            "sub": "smoke-test",
            "email": "smoke@test.local",
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description="AEO API smoke test")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SMOKE_TEST_BASE_URL", "http://127.0.0.1:8000"),
        help="API base URL (default: SMOKE_TEST_BASE_URL or localhost:8000)",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        default=os.environ.get("SMOKE_TEST_SKIP_SEED", "").lower() in ("1", "true", "yes"),
        help="Skip local DB init/seed (use for production Railway URL)",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    is_local = "127.0.0.1" in base or "localhost" in base

    settings = get_settings()
    if is_local and not args.skip_seed:
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
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=60) as client:
        health = await client.get("/health")
        print(f"GET /health -> {health.status_code} {health.text[:200]}")
        if health.status_code != 200:
            return 1

        paths = (
            "/api/brands",
            "/api/content/queue",
            "/api/content/drafts",
            "/api/reports/dashboard",
            "/api/notifications",
        )
        for path in paths:
            resp = await client.get(path)
            print(f"GET {path} -> {resp.status_code}")
            if resp.status_code not in (200, 401):
                print(resp.text[:500])
                return 1
            if resp.status_code == 401:
                print("  (401 — set SUPABASE_JWT_SECRET locally to match Railway for auth tests)")

    print(f"Smoke test passed against {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
