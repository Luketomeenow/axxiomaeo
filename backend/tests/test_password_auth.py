"""Password sign-in (AUTH_PROVIDER=password, the Azure deploy). Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_password_auth.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update(
    AUTH_PROVIDER="password",
    DASHBOARD_PASSWORD="correct horse battery staple",
    DASHBOARD_SESSION_SECRET="s" * 48,
    # Never reach a real database from a test: DB_PASSWORD + SUPABASE_DB_REGION in a
    # local .env would otherwise build a pooler URL that wins over DATABASE_URL.
    DATABASE_URL="postgresql://u:p@127.0.0.1:1/none",
    DB_PASSWORD="",
    SUPABASE_DB_REGION="",
    AZURE_PG_USER="",
    SCHEDULER_ENABLED="false",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()
from app.main import create_app  # noqa: E402

# base_url https so the Secure cookie is sent back, as it is on Azure.
client = TestClient(create_app(), base_url="https://testserver", raise_server_exceptions=False)


def test_api_requires_a_session():
    r = client.get("/api/brands")
    assert r.status_code == 401, r.text


def test_wrong_password_is_refused():
    r = client.post("/api/auth/login", json={"password": "nope"})
    assert r.status_code == 401
    assert "aeo_session" not in r.cookies


def test_right_password_signs_in_and_out():
    r = client.post("/api/auth/login", json={"password": "correct horse battery staple"})
    assert r.status_code == 200, r.text
    cookie = r.headers.get("set-cookie", "")
    assert "aeo_session=" in cookie and "HttpOnly" in cookie and "Secure" in cookie
    assert client.get("/api/auth/me").json()["authenticated"] is True
    # Past the auth check: without a database the API answers 503, never 401.
    assert client.get("/api/brands").status_code != 401
    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_forged_cookie_is_refused():
    import jwt

    forged = jwt.encode({"sub": "dashboard", "aud": "aeo-dashboard"}, "x" * 48, algorithm="HS256")
    c = TestClient(create_app(), base_url="https://testserver", raise_server_exceptions=False)
    c.cookies.set("aeo_session", forged)
    assert c.get("/api/brands").status_code == 401


def test_bearer_tokens_do_not_bypass_password_mode():
    c = TestClient(create_app(), base_url="https://testserver", raise_server_exceptions=False)
    assert c.get("/api/brands", headers={"Authorization": "Bearer anything"}).status_code == 401


def test_agent_api_still_uses_its_key():
    # Not behind the dashboard session; guarded by AGENT_API_KEY instead.
    assert client.get("/api/agent/overview").status_code in (401, 403, 503)


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
