"""Post-generation enrichment: internal links, author byline."""
import html as html_module
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.models.brand import Brand


AUTHOR_BYLINE_HTML = (
    '<p class="aeo-author-byline"><em>By {author_name}, '
    "IUEC-Certified Elevator Technician at {brand_name}</em></p>"
)


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


def ensure_tldr_block(html: str, target_query: str) -> str:
    if "aeo-tldr" in html:
        return html
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body") or soup
    tldr = soup.new_tag("div", attrs={"class": "aeo-tldr"})
    tldr.string = f"Quick answer: See the opening paragraph for {target_query}."
    h1 = body.find("h1")
    if h1:
        h1.insert_after(tldr)
    return str(soup)


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
