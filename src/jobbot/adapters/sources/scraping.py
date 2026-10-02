"""Helpers for HTML scrapers. Selectors drift; keep parsing forgiving."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser, Node

_AT_RE = re.compile(r"^(?P<title>.+?)\s+at\s+(?P<company>.+)$", re.IGNORECASE)


def text_of(node: Node | None) -> str:
    return node.text(separator=" ", strip=True) if node is not None else ""


def first(node: Node, *selectors: str) -> Node | None:
    for selector in selectors:
        found = node.css_first(selector)
        if found is not None:
            return found
    return None


def split_title_company(text: str) -> tuple[str, str]:
    """'Backend Developer at Acme Ltd' -> ('Backend Developer', 'Acme Ltd')."""
    match = _AT_RE.match(text.strip())
    if match:
        return match["title"].strip(), match["company"].strip()
    return text.strip(), ""


def job_links(html: str, base_url: str, href_pattern: re.Pattern) -> list[tuple[str, str]]:
    """Fallback: every (absolute_url, anchor_text) whose href looks like a job page."""
    tree = HTMLParser(html)
    seen: set[str] = set()
    out = []
    for a in tree.css("a[href]"):
        href = a.attributes.get("href") or ""
        if not href_pattern.search(href):
            continue
        url = urljoin(base_url, href)
        label = text_of(a)
        if url in seen or len(label) < 4:
            continue
        seen.add(url)
        out.append((url, label))
    return out
