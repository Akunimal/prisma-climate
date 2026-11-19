"""Tests for the lightweight HTML view at /basic/ (site/index.html).

Ensures accessibility, dark theme support, anti-FOUC script, zero external CDNs,
safe localStorage isolation from Flutter keys, and operational gate respect.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path


class _BasicHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.buttons: list[dict[str, str]] = []
        self.scripts: list[str] = []
        self.external_links: list[str] = []
        self._current_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attr_dict = {k: v or "" for k, v in attrs}
        if tag == "button":
            self.buttons.append(attr_dict)
        if tag in ("script", "link", "img"):
            src = attr_dict.get("src") or attr_dict.get("href")
            if src and (
                src.startswith("http://")
                or src.startswith("https://")
                or src.startswith("//")
            ):
                self.external_links.append(src)


def _load_site_html() -> str:
    path = Path(__file__).resolve().parents[2] / "site" / "index.html"
    assert path.is_file(), f"site/index.html not found at {path}"
    return path.read_text(encoding="utf-8")


def test_site_html_structure_and_no_external_resources() -> None:
    html = _load_site_html()
    parser = _BasicHtmlParser()
    parser.feed(html)

    # Basic essential tags
    assert "html" in parser.tags
    assert "head" in parser.tags
    assert "body" in parser.tags
    assert "header" in parser.tags
    assert "main" in parser.tags
    assert "footer" in parser.tags

    # Zero external CDN script or stylesheet dependencies (privacy & offline friendliness)
    msg = f"Found unexpected external resources: {parser.external_links}"
    assert not parser.external_links, msg


def test_dark_theme_css_tokens_and_media_query() -> None:
    html = _load_site_html()

    # CSS variables in :root
    assert "--bg:" in html
    assert "--panel:" in html
    assert "--ink:" in html
    assert "--muted:" in html
    assert "--line:" in html
    assert "--accent:" in html
    assert "--bar-bg:" in html

    # Dark mode media query and explicit attribute
    assert "@media (prefers-color-scheme: dark)" in html
    assert '[data-theme="dark"]' in html
    assert "color-scheme: light dark" in html


def test_anti_fouc_script_in_head() -> None:
    html = _load_site_html()
    head_match = re.search(r"<head>(.*?)</head>", html, re.DOTALL)
    assert head_match is not None
    head_content = head_match.group(1)

    # Anti-FOUC synchronous script exists in <head>
    assert "prisma_basic_theme" in head_content
    assert "data-theme" in head_content
    assert "localStorage.getItem" in head_content


def test_theme_toggle_accessibility_and_local_storage_safety() -> None:
    html = _load_site_html()
    parser = _BasicHtmlParser()
    parser.feed(html)

    # Theme toggle button exists with accessibility attributes
    toggle = next((b for b in parser.buttons if b.get("id") == "theme-toggle"), None)
    assert toggle is not None, "id='theme-toggle' button missing"
    assert toggle.get("type") == "button"
    assert "aria-label" in toggle
    assert "theme" in toggle["aria-label"].lower()

    # localStorage access is strictly safe (wrapped in try-catch)
    assert "try {" in html and "localStorage" in html
    assert "catch" in html

    # Never writes or tampers with Flutter keys
    assert "flutter." not in html


def test_operational_gate_note_integrity() -> None:
    html = _load_site_html()
    # Respects 15-issue-date gate rule
    assert "15-issue-date gate" in html
    assert "EVALUATION_PROTOCOL.md" in html
