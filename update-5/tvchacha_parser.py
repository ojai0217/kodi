#!/usr/bin/env python3
"""Extract .m3u8 stream URL(s) and related episode URLs from a webpage URL.

Published update marker: 2026-09-19-01 (proves the self-update mechanism
actually replaces this file; no functional change from the bundled copy).
"""
import json
import re
import sys
import urllib.parse
import urllib.request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

PLAYER_CONFIG_RE = re.compile(r"player_aaaa\s*=\s*(\{.*?\})\s*</script>", re.DOTALL)
M3U8_URL_RE = re.compile(r"https?:(?:\\/\\/|//)[^\s\"'\\]+?\.m3u8[^\s\"'\\]*")
EPISODE_LINK_RE = re.compile(
    r'<a[^>]*href="([^"]*/vod/play/id/\d+/sid/\d+/nid/\d+/)"[^>]*>\s*([^<]*?)\s*</a>'
)
SHOW_ITEM_RE = re.compile(
    r'<a class="aplusexp" href="([^"]+)" title="([^"]*)">'
    r'<div[^>]*data-original="([^"]*)"'
)
CATEGORY_RE = re.compile(
    r'<h2 class="title">([^<]*)</h2>.*?<a class="more" href="([^"]+)"',
    re.DOTALL,
)
PAGE_TIP_RE = re.compile(r"현재(\d+)/(\d+)페이지")


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _from_player_config(html: str) -> str | None:
    match = PLAYER_CONFIG_RE.search(html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    url = data.get("url")
    if url and ".m3u8" in url:
        return url.replace("\\/", "/")
    return None


def extract_m3u8_urls(html: str) -> list[str]:
    """Return all distinct m3u8 URLs found on the page, best match first."""
    urls = []

    config_url = _from_player_config(html)
    if config_url:
        urls.append(config_url)

    for raw in M3U8_URL_RE.findall(html):
        clean = raw.replace("\\/", "/")
        if clean not in urls:
            urls.append(clean)

    return urls


def extract_m3u8(url: str) -> str:
    """Fetch the page and return the first (best) m3u8 URL found."""
    html = fetch_html(url)
    urls = extract_m3u8_urls(html)
    if not urls:
        raise ValueError(f"no m3u8 url found on page: {url}")
    return urls[0]


def extract_related_urls(html: str, base_url: str) -> list[dict]:
    """Return related episode links (e.g. other nid values) found on the page.

    Each item is {"url": <absolute url>, "label": <link text>}, in page order,
    de-duplicated by url.
    """
    seen = set()
    episodes = []
    for href, label in EPISODE_LINK_RE.findall(html):
        abs_url = urllib.parse.urljoin(base_url, href)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        episodes.append({"url": abs_url, "label": label.strip()})
    return episodes


def get_related_urls(url: str) -> list[dict]:
    """Fetch the page and return its related episode URLs."""
    html = fetch_html(url)
    return extract_related_urls(html, url)


def extract_categories(html: str, base_url: str) -> list[dict]:
    """Return top-level categories from the home page.

    Each item is {"title": str, "url": <absolute url>}, in page order.
    """
    categories = []
    for title, href in CATEGORY_RE.findall(html):
        categories.append({
            "title": title.strip(),
            "url": urllib.parse.urljoin(base_url, href),
        })
    return categories


def get_categories(base_url: str = "https://tvchacha05.live/") -> list[dict]:
    """Fetch the home page and return its top-level categories."""
    html = fetch_html(base_url)
    return extract_categories(html, base_url)


def get_page_info(html: str) -> tuple[int, int] | None:
    """Return (current_page, total_pages) from a show-list page, or None."""
    match = PAGE_TIP_RE.search(html)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def has_next_page(html: str) -> bool:
    """True if a show-list page has more pages after it."""
    info = get_page_info(html)
    if info is None:
        return False
    current, total = info
    return current < total


def extract_show_list(html: str, base_url: str) -> list[dict]:
    """Return shows listed on a show page.

    Each item is {"title": str, "thumbnail": str, "url": <absolute url>}.
    """
    shows = []
    for href, title, thumbnail in SHOW_ITEM_RE.findall(html):
        shows.append({
            "title": title,
            "thumbnail": thumbnail,
            "url": urllib.parse.urljoin(base_url, href),
        })
    return shows


def get_show_list(show_id, page: int = 1) -> list[dict]:
    """Fetch a show list page and return its shows.

    e.g. get_show_list(3, 1) -> shows on
    https://tvchacha05.live/index.php/vod/show/id/3/page/1/
    """
    url = f"https://tvchacha05.live/index.php/vod/show/id/{show_id}/page/{page}/"
    html = fetch_html(url)
    return extract_show_list(html, url)


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <page-url>", file=sys.stderr)
        sys.exit(1)
    page_url = sys.argv[1]
    html = fetch_html(page_url)

    urls = extract_m3u8_urls(html)
    if not urls:
        print("no m3u8 url found", file=sys.stderr)
    for u in urls:
        print(u)

    related = extract_related_urls(html, page_url)
    if related:
        print(f"\n{len(related)} related url(s):", file=sys.stderr)
        for ep in related:
            print(f"  {ep['label']}: {ep['url']}", file=sys.stderr)


if __name__ == "__main__":
    main()
