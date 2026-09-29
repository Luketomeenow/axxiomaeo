"""Dashboard + API on one origin (the Azure deploy). Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_frontend_mount.py

The dashboard's Documentation page lives at /docs, which is also FastAPI's
default Swagger UI path. When the backend serves the dashboard, Swagger must
move under /api, or a refresh (or a shared /docs?tab=azure link) opens Swagger.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
DIST = Path(tempfile.mkdtemp(prefix="aeo-dist-"))
(DIST / "index.html").write_text("<!doctype html><title>AEO dashboard</title>")
os.environ.update(
    FRONTEND_DIST_DIR=str(DIST),
    # Never reach a real database from a test (see test_password_auth.py).
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

client = TestClient(create_app(), raise_server_exceptions=False)


def _is_dashboard(r) -> bool:
    return r.status_code == 200 and "AEO dashboard" in r.text


def test_docs_is_the_dashboard_page():
    assert _is_dashboard(client.get("/docs"))
    assert _is_dashboard(client.get("/docs?tab=azure"))


def test_swagger_moves_under_api():
    r = client.get("/api/docs")
    assert r.status_code == 200 and "swagger" in r.text.lower(), r.text[:200]
    assert client.get("/api/redoc").status_code == 200


def test_spa_fallback_and_api_404s():
    assert _is_dashboard(client.get("/citations"))
    r = client.get("/api/no-such-route")
    assert r.status_code == 404 and not _is_dashboard(r)


def test_without_dashboard_swagger_stays_at_docs():
    os.environ["FRONTEND_DIST_DIR"] = ""
    get_settings.cache_clear()
    try:
        api_only = TestClient(create_app(), raise_server_exceptions=False)
        r = api_only.get("/docs")
        assert r.status_code == 200 and "swagger" in r.text.lower(), r.text[:200]
    finally:
        os.environ["FRONTEND_DIST_DIR"] = str(DIST)
        get_settings.cache_clear()


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
