"""CTA / phone refresh tests (no database, no network). Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_cta_refresh.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update(
    DATABASE_URL="postgresql://u:p@127.0.0.1:1/none",
    DB_PASSWORD="",
    SUPABASE_DB_REGION="",
    AZURE_PG_USER="",
    SCHEDULER_ENABLED="false",
)

from app.models.brand import Brand  # noqa: E402
from app.services.content_enrichment import ensure_cta_block, find_contact_url  # noqa: E402
from app.services.cta_refresh_service import (  # noqa: E402
    cta_numbers,
    phone_digits,
    refresh_cta_and_phone,
)

POOL = "301-307-5363"  # a CallRail website-pool number (what the posts showed)
MAIN = "301-779-9116"  # the swap target the CallRail script replaces per visitor
CONTACT = "https://qualityelevator.com/contact-us/"


def _brand(phone: str | None) -> Brand:
    return Brand(id="quality", name="Quality Elevator", wp_url="https://qualityelevator.com", phone=phone)


def _post(phone: str | None, contact_url: str | None = None) -> str:
    body = (
        "<h2>Who inspects elevators in Maryland?</h2>"
        "<p>Call us at (301) 307-5363 or <a href=\"tel:+13013075363\">tap to call</a>.</p>"
        "<p>The state elevator unit answers at 410-230-6230.</p>"
    )
    return ensure_cta_block(body, _brand(phone), contact_url)


def test_phone_digits():
    assert phone_digits("(844) 646-9660") == "8446469660"
    assert phone_digits("+1 844 646 9660") == "8446469660"
    assert phone_digits("tel:18446469660") == "8446469660"
    assert phone_digits("844-646-96601") is None  # 11 digits not starting with 1
    assert phone_digits("12345") is None
    assert phone_digits(None) is None


def test_pool_number_replaced_everywhere_else_untouched():
    html = _post(POOL)
    assert cta_numbers(html) == {"3013075363"}

    out, replaced = refresh_cta_and_phone(html, _brand(MAIN), CONTACT)
    assert replaced == {"3013075363"}
    digits_only = "".join(ch for ch in out if ch.isdigit())
    assert "3013075363" not in digits_only
    assert 'href="tel:3017799116"' in out  # the rebuilt CTA
    assert "Call 301-779-9116" in out
    assert "Call us at 301-779-9116" in out  # body text
    assert 'href="tel:3017799116">tap to call' in out  # body tel: link
    assert "410-230-6230" in out  # a third-party number is never touched
    assert 'class="aeo-cta-quote"' in out and CONTACT in out
    assert out.count('class="aeo-cta"') == 1

    # Idempotent: a refreshed post is left alone.
    again, replaced_again = refresh_cta_and_phone(out, _brand(MAIN), CONTACT)
    assert again == out and replaced_again == set()


def test_current_post_unchanged_and_missing_quote_link_added():
    html = _post(MAIN, CONTACT)
    out, replaced = refresh_cta_and_phone(html, _brand(MAIN), CONTACT)
    assert out == html and replaced == set()

    no_quote = _post(MAIN, None)
    out, replaced = refresh_cta_and_phone(no_quote, _brand(MAIN), CONTACT)
    assert replaced == set() and 'class="aeo-cta-quote"' in out


def test_post_without_cta_gets_one():
    out, _ = refresh_cta_and_phone("<p>Elevator inspections explained.</p>", _brand(MAIN), CONTACT)
    assert 'class="aeo-cta"' in out and "tel:3017799116" in out


def test_brand_without_phone_drops_the_old_number():
    html = _post(POOL)
    out, replaced = refresh_cta_and_phone(html, _brand(None), CONTACT)
    assert replaced == {"3013075363"}
    assert "307-5363" not in out and "tel:+1301" not in out
    assert "tap to call" in out  # link text kept, link removed
    assert 'class="aeo-cta-call"' not in out and 'class="aeo-cta-quote"' in out


def test_named_old_number_in_body_only():
    html = "<p>Questions? Call 301.307.5363.</p>" + ensure_cta_block("", _brand(MAIN), None)
    out, replaced = refresh_cta_and_phone(html, _brand(MAIN), None, {"3013075363"})
    assert replaced == {"3013075363"} and "Call 301-779-9116." in out


def test_find_contact_url_prefers_contact_then_support():
    support = {"slug": "customer-support", "title": "Customer Support", "url": "https://az/support/"}
    contact = {"slug": "contact-us", "title": "Contact Us", "url": "https://az/contact-us/"}
    about = {"slug": "about", "title": "About", "url": "https://az/about/"}
    assert find_contact_url([about, support]) == "https://az/support/"
    assert find_contact_url([support, contact]) == "https://az/contact-us/"
    assert find_contact_url([about]) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
