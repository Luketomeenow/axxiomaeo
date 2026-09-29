"""Dashboard sign-in endpoints for AUTH_PROVIDER=password (the Azure deploy).

One shared dashboard password, the model the marketing hub uses, kept in
Azure Key Vault. A correct password gets a signed HttpOnly session cookie;
every /api route then checks it through app.auth.get_current_user. Repeated
wrong passwords lock that client out for a while. Under AUTH_PROVIDER=supabase
(Railway) these endpoints report the provider and do nothing else.
"""
import asyncio
import hmac
import time

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.auth import SESSION_COOKIE, issue_session, password_auth_enabled, verify_session
from app.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_MAX_FAILURES = 8
_LOCKOUT_SECONDS = 15 * 60
_failures: dict[str, list[float]] = {}


class LoginRequest(BaseModel):
    password: str


def _client(request: Request) -> str:
    # App Service puts the real client first in X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown"))


def _locked(client: str) -> bool:
    now = time.time()
    recent = [t for t in _failures.get(client, []) if now - t < _LOCKOUT_SECONDS]
    _failures[client] = recent
    return len(recent) >= _MAX_FAILURES


@router.get("/me")
async def me(request: Request):
    if not password_auth_enabled():
        return {"provider": "supabase"}
    try:
        user = verify_session(request.cookies.get(SESSION_COOKIE))
    except HTTPException:
        return {"provider": "password", "authenticated": False}
    return {"provider": "password", "authenticated": True, "user": user}


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    if not password_auth_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    expected = get_settings().dashboard_password
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard sign-in is not configured (DASHBOARD_PASSWORD missing)",
        )
    client = _client(request)
    if _locked(client):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many wrong passwords. Try again in 15 minutes.",
        )
    if not hmac.compare_digest(body.password.encode(), expected.encode()):
        _failures.setdefault(client, []).append(time.time())
        await asyncio.sleep(1)  # slow down guessing
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong password")
    _failures.pop(client, None)
    token, ttl = issue_session()
    response.set_cookie(
        SESSION_COOKIE, token, max_age=ttl, httponly=True, secure=True, samesite="lax", path="/"
    )
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return {"ok": True}
