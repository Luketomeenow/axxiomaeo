import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import get_settings

security = HTTPBearer(auto_error=False)
_jwk_client: PyJWKClient | None = None

JWKS_ALGORITHMS = ("ES256", "RS256")


def _get_jwk_client() -> PyJWKClient | None:
    global _jwk_client
    settings = get_settings()
    jwks_url = settings.supabase_jwks_url
    if not jwks_url and settings.supabase_url:
        jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    if jwks_url:
        _jwk_client = PyJWKClient(jwks_url)
    return _jwk_client


def _decode_with_jwks(token: str) -> dict:
    client = _get_jwk_client()
    if not client:
        raise jwt.PyJWTError("JWKS not configured")

    signing_key = client.get_signing_key_from_jwt(token)
    header = jwt.get_unverified_header(token)
    alg = header.get("alg")
    if alg not in JWKS_ALGORITHMS:
        raise jwt.PyJWTError(f"Unsupported JWKS algorithm: {alg}")

    return jwt.decode(
        token,
        signing_key.key,
        algorithms=[alg],
        audience="authenticated",
    )


def _decode_with_secret(token: str, secret: str) -> dict:
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience="authenticated",
    )


def verify_token(token: str) -> dict:
    settings = get_settings()
    # Fail closed: the no-auth dev shortcut requires an explicit opt-in flag,
    # so a deploy that forgets ENVIRONMENT/Supabase vars is never left open.
    if (
        settings.auth_dev_bypass
        and settings.environment == "development"
        and not settings.supabase_jwt_secret
        and not settings.supabase_url
    ):
        return {"sub": "dev-user", "email": "dev@localhost"}

    header_alg = jwt.get_unverified_header(token).get("alg")
    errors: list[str] = []

    # Supabase user access tokens are ES256/RS256 — verify via JWKS first.
    if header_alg in JWKS_ALGORITHMS and settings.supabase_url:
        try:
            return _decode_with_jwks(token)
        except jwt.PyJWTError as e:
            errors.append(str(e))

    if settings.supabase_jwt_secret:
        try:
            return _decode_with_secret(token, settings.supabase_jwt_secret)
        except jwt.PyJWTError as e:
            errors.append(str(e))

    if header_alg == "HS256" and not settings.supabase_jwt_secret:
        errors.append("SUPABASE_JWT_SECRET not configured for HS256 token")

    if header_alg in JWKS_ALGORITHMS and not settings.supabase_url:
        errors.append("SUPABASE_URL not configured for JWKS verification")

    detail = errors[0] if errors else "Auth not configured"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {detail}")


# --- password sign-in (AUTH_PROVIDER=password, the Azure deploy) -----------

SESSION_COOKIE = "aeo_session"
_SESSION_AUDIENCE = "aeo-dashboard"
DASHBOARD_USER = {"sub": "dashboard", "email": "Dashboard login", "provider": "password"}


def password_auth_enabled() -> bool:
    return get_settings().auth_provider.strip().lower() == "password"


def _session_secret() -> str:
    secret = get_settings().dashboard_session_secret
    if len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard sign-in is not configured (DASHBOARD_SESSION_SECRET missing)",
        )
    return secret


def issue_session() -> tuple[str, int]:
    """Signed session token and its lifetime in seconds."""
    import time

    ttl = max(1, get_settings().dashboard_session_hours) * 3600
    now = int(time.time())
    token = jwt.encode(
        {"sub": DASHBOARD_USER["sub"], "aud": _SESSION_AUDIENCE, "iat": now, "exp": now + ttl},
        _session_secret(),
        algorithm="HS256",
    )
    return token, ttl


def verify_session(token: str | None) -> dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    try:
        jwt.decode(token, _session_secret(), algorithms=["HS256"], audience=_SESSION_AUDIENCE)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired — sign in again")
    return dict(DASHBOARD_USER)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if password_auth_enabled():
        return verify_session(request.cookies.get(SESSION_COOKIE))
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header")
    return verify_token(credentials.credentials)


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None
