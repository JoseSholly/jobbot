from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobbot.domain.models import Profile

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_json():
    return lambda name: json.loads((FIXTURES / name).read_text())


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text()


@pytest.fixture
def backend_profile() -> Profile:
    return Profile(
        target_titles=["Backend Engineer", "Python Developer", "Django Developer"],
        skills=["Python", "Django", "DRF", "PostgreSQL", "Docker", "Redis", "Celery"],
        seniority=["mid", "senior", "lead"],
        remote_ok=True,
        countries_ok=["Nigeria", "Worldwide", "Africa", "EMEA"],
        exclude_keywords=["unpaid", "internship", "PHP"],
        summary="Backend engineer building Python and Django REST APIs with PostgreSQL and Docker.",
    )
