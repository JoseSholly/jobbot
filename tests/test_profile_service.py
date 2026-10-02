import pytest

from jobbot.adapters.memory import MemoryProfileRepository
from jobbot.domain.models import Profile
from jobbot.services.cv_parser import extract_skills, extract_titles, heuristic_profile
from jobbot.services.profile import ProfileBuildError, ProfileService
from tests.fakes import FakeDownloader, FakeExtractor, FakeLLM, RecordingNotifier

CV = """Jane Doe
Senior Backend Engineer
Lagos, Nigeria | jane@example.com

Summary
Backend engineer with 6 years of experience building REST APIs with Python, Django and
Django REST Framework. Comfortable with PostgreSQL, Redis, Celery, Docker and AWS.

Experience
Backend Engineer | Paystack-like Co | 2021 - 2026
- Built payment APIs in Django and PostgreSQL
Python Developer | Agency | 2019 - 2021
"""


def test_heuristic_parser():
    profile = heuristic_profile(CV)
    assert "Senior Backend Engineer" in profile.target_titles
    assert {"Python", "Django", "PostgreSQL", "Docker", "AWS"} <= set(profile.skills)
    assert "Django REST Framework" in profile.skills
    assert "senior" in profile.seniority
    assert profile.summary


def test_extractors_ignore_noise():
    assert extract_titles("2019 - 2021 Engineer at X 2020\nHello") == []
    assert extract_skills("I like golang and gophers") == ["Golang"]
    assert extract_skills("Spring Boot services") == ["Spring Boot"]


async def test_parse_prefers_llm_and_fills_gaps():
    llm = FakeLLM(Profile(target_titles=["Staff Engineer"], skills=[], summary="LLM summary"))
    service = ProfileService(MemoryProfileRepository(), llm=llm)
    profile = await service.parse(CV)
    assert profile.target_titles == ["Staff Engineer"]
    assert "Python" in profile.skills  # filled from heuristic
    assert profile.summary == "LLM summary"


async def test_parse_falls_back_when_llm_fails():
    service = ProfileService(MemoryProfileRepository(), llm=FakeLLM(fail=True))
    assert "Python" in (await service.parse(CV)).skills


async def test_parse_rejects_empty_pdf_text():
    with pytest.raises(ProfileBuildError):
        await ProfileService(MemoryProfileRepository()).parse("   ")


async def test_new_cv_keeps_user_preferences():
    repo = MemoryProfileRepository(
        {5: Profile(countries_ok=["Nigeria"], remote_ok=False, exclude_keywords=["crypto"])}
    )
    profile = await ProfileService(repo).build_from_text(5, CV)
    assert profile.countries_ok == ["Nigeria"] and profile.remote_ok is False
    assert "crypto" in profile.exclude_keywords and "unpaid" in profile.exclude_keywords
    assert repo.cv_texts[5].startswith("Jane Doe")


async def test_build_from_upload_notifies_user():
    repo = MemoryProfileRepository()
    repo.cv_file_ids[7] = "FILE"
    notifier = RecordingNotifier()
    service = ProfileService(
        repo, downloader=FakeDownloader(), notifier=notifier, extractor=FakeExtractor(CV)
    )
    await service.build_from_upload(7)
    assert repo.get(7).skills
    assert "Profile ready" in notifier.texts_for(7)[0]


async def test_build_from_upload_reports_unreadable_pdf():
    repo = MemoryProfileRepository()
    repo.cv_file_ids[7] = "FILE"
    notifier = RecordingNotifier()
    service = ProfileService(
        repo, downloader=FakeDownloader(), notifier=notifier, extractor=FakeExtractor("")
    )
    with pytest.raises(ProfileBuildError):
        await service.build_from_upload(7)
    assert "couldn't read text" in notifier.texts_for(7)[0]
