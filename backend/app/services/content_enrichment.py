"""Post-generation enrichment: internal links, author byline."""
import html as html_module
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.models.brand import Brand


AUTHOR_BYLINE_HTML = (
    '<p class="aeo-author-byline"><em>By {author_name}, '
    "IUEC-Certified Elevator Technician at {brand_name}</em></p>"
)

# Unresolved phone token, optionally with a leading "at"/"on" so CTAs like
# "Call us at [BRAND_PHONE] today" degrade to "Call us today".
_PHONE_TOKEN_RE = re.compile(r"(?:\s+(?:at|on)\s+)?\(?\[BRAND_PHONE\]\)?", re.IGNORECASE)


def strip_phone_placeholder(html: str) -> str:
    """Remove unresolved [BRAND_PHONE] tokens so the literal placeholder never
    reaches published HTML when a brand has no phone configured."""
    if "[BRAND_PHONE]" not in html:
        return html
    cleaned = _PHONE_TOKEN_RE.sub("", html)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return re.sub(r"\s+([,.])", r"\1", cleaned)


def ensure_author_byline(html: str, brand: Brand, author_name: str | None = None) -> str:
    if "aeo-author-byline" in html:
        return html
    name = author_name or f"{brand.name} Technical Team"
    byline = AUTHOR_BYLINE_HTML.format(author_name=name, brand_name=brand.name)
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body") or soup
    first = body.find(["h1", "p", "div"])
    if first:
        first.insert_before(BeautifulSoup(byline, "lxml"))
    else:
        body.insert(0, BeautifulSoup(byline, "lxml"))
    return str(soup)


def ensure_tldr_block(html: str, target_query: str, max_words: int = 60) -> str:
    """Guarantee an aeo-tldr block with a real answer.

    When the model omitted the block, summarize from the first substantive
    paragraph (the answer-first opener) instead of emitting placeholder text.
    If there is nothing to summarize, skip the block entirely.
    """
    if "aeo-tldr" in html:
        return html
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body") or soup

    summary = ""
    for p in body.find_all("p"):
        if "aeo-author-byline" in " ".join(p.get("class") or []):
            continue
        text = p.get_text(" ", strip=True)
        if len(text) >= 40:
            summary = text
            break
    if not summary:
        return html

    words = summary.split()
    if len(words) > max_words:
        summary = " ".join(words[:max_words]).rstrip(",;:") + "…"

    tldr = soup.new_tag("div", attrs={"class": "aeo-tldr"})
    tldr.string = f"Quick answer: {summary}"
    h1 = body.find("h1")
    if h1:
        h1.insert_after(tldr)
    else:
        body.insert(0, tldr)
    return str(soup)


def normalize_article_headings(html: str, title: str = "") -> str:
    """Keep the article body free of <h1> so the page has exactly one H1.

    The generator emits an <h1> (used as the anchor for the TL;DR box), but
    WordPress/the theme already renders the post title as the page H1 — so a
    body H1 that repeats the title is a duplicate-H1 structural error. We drop a
    body H1 that matches the title, and demote any other stray H1 to H2 so the
    heading hierarchy stays valid (one H1 = the CMS title, the rest H2+).
    """
    if "<h1" not in html.lower():
        return html

    def _norm(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip()).lower().rstrip("?").strip()

    norm_title = _norm(title)
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body") or soup
    for h1 in body.find_all("h1"):
        if norm_title and _norm(h1.get_text()) == norm_title:
            h1.decompose()  # duplicate of the CMS-rendered title
        else:
            h1.name = "h2"  # keep the content, fix the level
    return str(soup)


# Leftover markdown links the model emits despite "HTML only" — [text](url),
# where url is an http(s) link or a site-relative /path. Bare fragments (#ref)
# and scheme-less parens are ignored so footnotes/prose aren't touched.
_MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+|/[^\s)]*)\)")
# Trailing characters that break an href when the model runs a URL into prose
# or a markdown bracket (the "…/]" 404s came from exactly this).
_HREF_TRAILING_JUNK = "]).,;:'\"“”’"


def _brand_host(brand: Brand) -> str:
    return urlparse(getattr(brand, "wp_url", "") or "").netloc.lower().replace("www.", "")


def _clean_href(href: str) -> str:
    href = (href or "").strip()
    while href and href[-1] in _HREF_TRAILING_JUNK:
        href = href[:-1]
    return href.strip()


def _internal_path(url: str, brand_host: str) -> str | None:
    """Site-relative path if the URL is internal (relative or same host), else None."""
    parsed = urlparse(url)
    if not parsed.scheme and not parsed.netloc:
        return (parsed.path or "/").rstrip("/") or "/"
    if parsed.scheme in ("http", "https") and parsed.netloc.lower().replace("www.", "") == brand_host:
        return (parsed.path or "/").rstrip("/") or "/"
    return None


def sanitize_links(html: str, brand: Brand, known_paths: set[str] | None = None) -> str:
    """Strip broken / invented links from generated content before publish.

    - Converts stray markdown links ``[text](url)`` to real anchors.
    - Trims malformed hrefs (trailing ``] ) . ,`` etc.) — the cause of the
      ``…/]`` 404s.
    - Drops empty / ``javascript:`` links (keeps the text).
    - Keeps external links and ``#`` / ``mailto:`` / ``tel:`` as-is.
    - Internal links: when ``known_paths`` is given (generation / backfill),
      an internal link whose path isn't a real published page is unwrapped —
      the anchor text stays, the dead link goes. When ``known_paths`` is None
      (a lightweight publish-time pass) internal links are only cleaned, not
      existence-checked, so verified links added earlier aren't stripped.
    """
    if not html:
        return html

    converted = _MD_LINK_RE.sub(r'<a href="\2">\1</a>', html)
    changed = converted != html
    soup = BeautifulSoup(converted, "lxml")
    host = _brand_host(brand)
    validate_internal = known_paths is not None
    known = known_paths or set()

    for a in soup.find_all("a"):
        raw = a.get("href", "")
        href = _clean_href(raw)

        if href.startswith(("#", "mailto:", "tel:")):
            if href != raw:
                a["href"] = href
                changed = True
            continue
        if not href or href.lower().startswith("javascript:"):
            a.unwrap()
            changed = True
            continue

        path = _internal_path(href, host)
        if path is None:  # external link — trust (prompt limits these to authoritative sources)
            if href != raw:
                a["href"] = href
                changed = True
            continue

        if not validate_internal or path == "/" or path in known:
            if href != raw:
                a["href"] = href
                changed = True
        else:
            a.unwrap()  # invented/broken internal link → keep the words, drop the 404
            changed = True

    # Return the original string untouched when nothing changed, so a valid
    # post isn't needlessly re-serialized (and the backfill won't re-publish it).
    return str(soup) if changed else html


def inject_internal_links(
    html: str,
    brand: Brand,
    related: list[dict],
    max_links: int = 5,
) -> str:
    """Append a Related Resources section with links to published posts/pages."""
    if not related or "aeo-related-resources" in html:
        return html

    base = brand.wp_url.rstrip("/")
    items = []
    for page in related[:max_links]:
        url = page.get("url") or urljoin(base + "/", page.get("slug", ""))
        title = page.get("title", page.get("slug", "Related page"))
        items.append(f'<li><a href="{url}">{title}</a></li>')

    if not items:
        return html

    block = (
        '<section class="aeo-related-resources">'
        "<h2>Related resources from {brand}</h2><ul>{items}</ul></section>"
    ).format(brand=brand.name, items="".join(items))

    return html.rstrip() + "\n" + block


def count_faq_pairs(html: str) -> int:
    h2_pattern = re.compile(r"<h2[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
    return sum(1 for h in h2_pattern.findall(html) if h.strip().endswith("?"))


def query_terms_in_text(query: str, text: str, min_ratio: float = 0.3) -> bool:
    """True if enough query terms appear in opening text."""
    q_words = {w.lower() for w in re.findall(r"[a-z0-9]+", query) if len(w) > 3}
    if not q_words:
        return True
    text_lower = text.lower()
    hits = sum(1 for w in q_words if w in text_lower)
    return hits / len(q_words) >= min_ratio


def _figure_html(img: dict) -> str:
    url = html_module.escape(img["url"], quote=True)
    alt = html_module.escape(img.get("alt", ""), quote=True)
    title = html_module.escape(img.get("title", alt), quote=True)
    caption = html_module.escape(img.get("caption", alt))
    return (
        '<figure class="aeo-figure" itemscope itemtype="https://schema.org/ImageObject">'
        f'<img src="{url}" alt="{alt}" title="{title}" loading="lazy" '
        f'itemprop="contentUrl" class="aeo-content-image" />'
        f'<figcaption itemprop="description">{caption}</figcaption>'
        "</figure>"
    )


def inject_content_images(html: str, images: list[dict]) -> str:
    """Insert uploaded images into HTML at planned placements."""
    if not images:
        return html
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body") or soup

    inline_idx = 0
    h2_tags = body.find_all("h2")

    for img in images:
        placement = img.get("placement", "after_h1")
        slot = img.get("slot", "")
        figure = BeautifulSoup(_figure_html(img), "lxml")

        if placement == "after_h1" or slot == "hero":
            anchor = body.find(class_="aeo-tldr") or body.find("h1")
            if anchor:
                anchor.insert_after(figure)
            else:
                body.insert(0, figure)
            continue

        h2_index = img.get("h2_index")
        if h2_index is None:
            h2_index = inline_idx
            inline_idx += 1
        if isinstance(h2_index, str) and h2_index.isdigit():
            h2_index = int(h2_index)
        if isinstance(h2_index, int) and 0 <= h2_index < len(h2_tags):
            h2_tags[h2_index].insert_after(figure)
        elif h2_tags:
            mid = min(len(h2_tags) // 2, len(h2_tags) - 1)
            h2_tags[mid].insert_after(figure)

    return str(soup)
