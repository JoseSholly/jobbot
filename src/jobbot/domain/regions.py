"""Location rules: is a job in Nigeria, and can someone in Nigeria take it?"""

from __future__ import annotations

import re

from jobbot.domain.text import contains_term

NIGERIA_TERMS = [
    "nigeria",
    "lagos",
    "abuja",
    "port harcourt",
    "ibadan",
    "kano",
    "enugu",
    "benin city",
    "kaduna",
    "abeokuta",
    "ikeja",
    "lekki",
    "victoria island",
    "owerri",
    "uyo",
    "calabar",
    "jos",
    "ilorin",
    "warri",
    "asaba",
    "akure",
    "osogbo",
    "fct",
]

OPEN_TERMS = ["worldwide", "anywhere", "global", "international", "any location"]
WANTS_OPEN = {"worldwide", "anywhere", "global"}
REGIONS_INCLUDING_NIGERIA = ["africa", "emea", "west africa", "sub-saharan africa"]
_FILLER_RE = re.compile(r"\b(remote|fully|100%|only|work from home|wfh)\b|[^a-z]+")


def is_nigerian(location: str) -> bool:
    loc = (location or "").lower()
    return any(contains_term(loc, term) for term in NIGERIA_TERMS)


def location_allows(location: str, countries_ok: list[str]) -> bool:
    """True if a job's location restriction is compatible with the user's accepted places.

    An empty location, or a bare "Remote", counts as unrestricted.
    """
    loc = (location or "").lower().strip()
    if not loc:
        return True
    wanted = [c.lower().strip() for c in countries_ok if c.strip()]
    if any(contains_term(loc, w) for w in wanted):
        return True
    if WANTS_OPEN.intersection(wanted):
        if any(contains_term(loc, t) for t in OPEN_TERMS):
            return True
        if not _FILLER_RE.sub("", loc):
            return True  # just "Remote"
    return "nigeria" in wanted and any(contains_term(loc, t) for t in REGIONS_INCLUDING_NIGERIA)
