"""Shared loader for the GOOGLE_SERVICE_ACCOUNT_JSON credential.

GA4Service and GSCService each decoded this env var independently and, when it
was malformed, silently returned zeros — dashboards and monthly reports then
showed 0 sessions/clicks with only a vague once-per-boot warning. This
centralizes the parsing (base64 or raw JSON, forgiving of quotes and missing
padding) and validates the payload actually IS a service-account key, logging
exactly what's wrong. The classic failure it catches: pasting an OAuth client
JSON ({"web": {...}}) instead of a service-account key file.
"""
import base64
import json
import logging

logger = logging.getLogger(__name__)

_FIX_HINT = (
    "Create a JSON key for a Google Cloud service account (IAM & Admin -> Service "
    "Accounts -> Keys), grant that account's client_email access to each GA4 property "
    "and Search Console site, then set GOOGLE_SERVICE_ACCOUNT_JSON to the base64 of "
    "the key file. GA4/GSC metrics read 0 until this is fixed."
)


def load_service_account_info(raw: str | None) -> dict | None:
    """Parse GOOGLE_SERVICE_ACCOUNT_JSON into service-account info, or None.

    Accepts base64-encoded JSON (the documented format) or raw JSON pasted
    directly; tolerates surrounding quotes and missing base64 padding. Returns
    None (with an actionable error log) rather than raising.
    """
    if not raw:
        return None
    cleaned = raw.strip().strip("'\"")

    info = None
    try:
        # validate=True so raw JSON isn't half-decoded into garbage bytes.
        padded = cleaned + "=" * (-len(cleaned) % 4)
        info = json.loads(base64.b64decode(padded, validate=True).decode())
    except Exception:
        try:
            info = json.loads(cleaned)
        except Exception:
            logger.error(
                "GOOGLE_SERVICE_ACCOUNT_JSON is neither base64-encoded JSON nor raw JSON. %s",
                _FIX_HINT,
            )
            return None

    if not isinstance(info, dict):
        logger.error("GOOGLE_SERVICE_ACCOUNT_JSON decodes to %s, not an object. %s", type(info).__name__, _FIX_HINT)
        return None
    if "web" in info or "installed" in info:
        logger.error(
            'GOOGLE_SERVICE_ACCOUNT_JSON contains an OAuth client JSON ("%s"), not a '
            "service-account key. %s",
            "web" if "web" in info else "installed",
            _FIX_HINT,
        )
        return None
    if info.get("type") != "service_account" or not info.get("client_email") or not info.get("private_key"):
        logger.error(
            "GOOGLE_SERVICE_ACCOUNT_JSON is missing service-account fields "
            "(type/client_email/private_key). %s",
            _FIX_HINT,
        )
        return None
    return info
