"""Heuristic CV -> Profile parser. Used when no LLM key is configured (or the LLM fails)."""

from __future__ import annotations

import re

from jobbot.domain.models import Profile
from jobbot.domain.skills import SENIORITY_WORDS, SKILLS, TITLE_WORDS
from jobbot.domain.text import contains_term

_LINE_SPLIT = re.compile(r"[\n\r]+")
_YEARS_RE = re.compile(r"(\d{1,2})\+?\s*(?:years|yrs)", re.IGNORECASE)


def extract_skills(text: str, limit: int = 25) -> list[str]:
    lower = text.lower()
    found = [s for s in SKILLS if contains_term(lower, s)]

    # Drop a generic skill whose every mention is inside a more specific one
    # (e.g. "Spring" when the CV only ever says "Spring Boot").
    def mentions(term: str) -> int:
        return len(re.findall(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9+#])", lower))

    def redundant(skill: str) -> bool:
        return any(
            other != skill and contains_term(other.lower(), skill) and mentions(skill) <= mentions(other)
            for other in found
        )

    return [s for s in found if not redundant(s)][:limit]


def extract_titles(text: str, limit: int = 4) -> list[str]:
    titles: list[str] = []
    for line in _LINE_SPLIT.split(text):
        clean = re.sub(r"[|•·–—]+", " ", line).strip(" -:\t")
        words = clean.split()
        if not 1 < len(words) <= 6:
            continue
        lower = clean.lower()
        if any(contains_term(lower, w) for w in TITLE_WORDS) and not re.search(r"\d{4}", clean):
            title = " ".join(w.capitalize() if w.islower() else w for w in words)
            if title.lower() not in {t.lower() for t in titles}:
                titles.append(title)
        if len(titles) >= limit:
            break
    return titles


def infer_seniority(text: str, titles: list[str]) -> list[str]:
    levels: set[str] = set()
    for title in titles:
        for word, level in SENIORITY_WORDS.items():
            if contains_term(title.lower(), word):
                levels.add(level)
    years = [int(m) for m in _YEARS_RE.findall(text)]
    if years:
        top = max(years)
        levels.add("senior" if top >= 5 else "mid" if top >= 2 else "junior")
    if not levels:
        levels = {"mid"}
    order = ["intern", "junior", "mid", "senior", "lead"]
    lowest = min(order.index(lvl) for lvl in levels)
    return order[lowest : lowest + 3]


def heuristic_profile(cv_text: str) -> Profile:
    text = cv_text or ""
    titles = extract_titles(text)
    skills = extract_skills(text)
    summary = re.sub(r"\s+", " ", text).strip()[:800]
    return Profile(
        target_titles=titles,
        skills=skills,
        seniority=infer_seniority(text, titles),
        summary=summary,
        exclude_keywords=["unpaid", "internship"],
    )
