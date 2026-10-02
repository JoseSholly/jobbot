"""Pure text helpers shared by services."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_BLOCK_TAG_RE = re.compile(r"</?(p|br|li|ul|ol|div|h[1-6]|tr)[^>]*>", re.IGNORECASE)
_NON_WORD_RE = re.compile(r"[^a-z0-9+#.]+")
_TRACKING_PARAMS = {
    "ref",
    "source",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "gh_src",
    "lever-source",
}


def strip_html(text: str) -> str:
    """Turn an HTML fragment into readable plain text."""
    if not text:
        return ""
    text = _BLOCK_TAG_RE.sub(" ", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    # Some APIs double-escape (e.g. Greenhouse "content").
    if "<" in text and ">" in text:
        text = _TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    return _WS_RE.sub(" ", text).strip()


def normalize_key(text: str) -> str:
    """Lowercase, accent-free, punctuation-free key used for dedupe."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"\(.*?\)", " ", text.lower())
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(inc|ltd|llc|limited|plc|gmbh|co|corp|the)\b", " ", text)
    return _WS_RE.sub(" ", text).strip()


def canonical_url(url: str) -> str:
    """Strip tracking params, fragments and trailing slashes so equal jobs share a URL."""
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in _TRACKING_PARAMS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def job_id_for(url: str) -> str:
    """Short stable id; fits easily in Telegram's 64-byte callback_data."""
    return hashlib.sha1(canonical_url(url).encode()).hexdigest()[:16]


def tokens(text: str) -> set[str]:
    return {t.strip(".") for t in _NON_WORD_RE.split((text or "").lower()) if len(t.strip(".")) > 1}


def contains_term(haystack_lower: str, term: str) -> bool:
    """Whole-word(ish) case-insensitive match that also works for 'C++', 'C#', 'Node.js'."""
    term = term.strip().lower()
    if not term:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9+#])"
    return re.search(pattern, haystack_lower) is not None


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
