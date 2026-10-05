"""CV parsing quality across professions + how the richer profile feeds search and ranking."""

from datetime import UTC, datetime

import pytest

from jobbot.adapters.gemini import CV_SCHEMA
from jobbot.adapters.memory import MemoryProfileRepository
from jobbot.domain.models import Profile
from jobbot.domain.roles import detect_families, remotive_categories_for
from jobbot.domain.synonyms import canonical, variants
from jobbot.services.cv_parser import heuristic_profile
from jobbot.services.ingestion import build_search_context
from jobbot.services.profile import ProfileService
from jobbot.services.scoring import profile_title_score, skill_score
from tests.fakes import FakeLLM, RecordingNotifier, job

NOW = datetime(2026, 10, 5, tzinfo=UTC)

CVS = {
    "frontend": """Ada Obi
Frontend Developer
Lagos, Nigeria
Frontend developer building responsive web apps with React, Next.js, TypeScript and Tailwind.
Experience: Frontend Developer at Shoplite (2022-2026). Built React dashboards and HTML/CSS pages.""",
    "va": """Bisi Ade
Virtual Assistant
Remote | Ibadan
Virtual assistant supporting founders with calendar management, email management, data entry and
customer support. Tools: Google Workspace, Microsoft Office, Notion, Trello, Zendesk, HubSpot.""",
    "content": """Chidi Eze
Content Creator
Content creator and social media manager growing brand pages on TikTok and Instagram.
Skills: copywriting, video editing with CapCut and Premiere Pro, SEO, content strategy,
social media management, community management.""",
    "design": """Dami Bello
Graphic Designer
Graphic designer focused on branding, logo design and social media graphics.
Tools: Photoshop, Illustrator, CorelDRAW, Canva, Figma, InDesign. Typography and motion graphics.""",
}


@pytest.mark.parametrize(
    "kind,title,skills,related",
    [
        ("frontend", "Frontend Developer", {"React", "TypeScript", "Tailwind"}, "React Developer"),
        (
            "va",
            "Virtual Assistant",
            {"Google Workspace", "Calendar Management", "Zendesk"},
            "Executive Assistant",
        ),
        (
            "content",
            "Content Creator",
            {"Copywriting", "Video Editing", "CapCut", "SEO"},
            "Social Media Manager",
        ),
        ("design", "Graphic Designer", {"Photoshop", "Illustrator", "Canva", "CorelDRAW"}, "UI/UX Designer"),
    ],
)
def test_heuristic_parser_handles_non_backend_professions(kind, title, skills, related):
    profile = heuristic_profile(CVS[kind])
    assert title in profile.target_titles
    assert skills <= set(profile.skills), profile.skills
    assert related in profile.related_titles
    assert title not in profile.related_titles


def test_role_families_and_categories():
    assert [f.name for f in detect_families(["Graphic Designer"], ["Canva"])][0] == "design"
    assert remotive_categories_for(["Virtual Assistant"], [])[:1] == ["customer-support"]
    assert "writing" in remotive_categories_for(["Content Creator"], ["Copywriting"])


def test_synonyms():
    assert canonical("drf") == "Django REST Framework"
    assert canonical("Adobe Photoshop") == "Photoshop"
    assert canonical("G Suite") == "Google Workspace"
    assert canonical("Some Niche Tool") == "Some Niche Tool"
    assert "Go" not in variants("Golang")  # short aliases only when the user wrote them
    assert "Go" in variants("Go")


def test_skill_score_matches_aliases():
    j = job("Backend Engineer", description="We use DRF, Postgres and K8s.")
    assert skill_score(j, ["Django REST Framework", "PostgreSQL", "Kubernetes"], 3) == 1.0
    d = job("Designer", description="Must know Adobe Photoshop and G Suite")
    assert skill_score(d, ["Photoshop", "Google Workspace"], 2) == 1.0


def test_related_titles_and_seniority_in_title_score():
    p = Profile(
        target_titles=["Senior Backend Engineer"],
        related_titles=["Python Developer"],
        seniority=["senior", "lead"],
    )
    assert profile_title_score("Python Developer", p) == pytest.approx(0.8)
    assert profile_title_score("Senior Backend Engineer", p) == 1.0
    mid = Profile(target_titles=["Backend Engineer"], seniority=["mid"])
    assert profile_title_score("Director of Backend Engineering", mid) < 0.5 * 1.01
    assert profile_title_score("Backend Engineer", mid) == 1.0
    va = Profile(target_titles=["Lead Generation Specialist"], seniority=["mid"])
    assert profile_title_score("Lead Generation Specialist", va) == 1.0  # not a 'lead' level


def test_search_context_uses_related_titles_and_categories():
    designer = Profile(
        target_titles=["Graphic Designer"], related_titles=["Brand Designer"], skills=["Canva"]
    )
    dev = Profile(target_titles=["Backend Engineer"], related_titles=["Python Developer"], skills=["Python"])
    ctx = build_search_context([designer, dev], max_keywords=10, max_skills=4)
    assert {"Brand Designer", "Python Developer"} <= set(ctx.keywords)
    assert {"design", "software-dev"} <= set(ctx.categories)


def test_profile_roundtrip_and_old_profiles_still_load():
    p = Profile(target_titles=["A"], related_titles=["B"], domains=["fintech"])
    assert Profile.from_dict(p.to_dict()) == p
    old = Profile.from_dict({"target_titles": ["X"], "skills": ["Y"]})
    assert old.related_titles == [] and old.domains == []
    assert "Industries: fintech" in p.embedding_text


def test_gemini_schema_lists_every_profile_field():
    assert set(CV_SCHEMA["properties"]) >= {
        "target_titles",
        "related_titles",
        "skills",
        "seniority",
        "domains",
        "summary",
    }
    assert CV_SCHEMA["properties"]["seniority"]["items"]["enum"] == [
        "intern",
        "junior",
        "mid",
        "senior",
        "lead",
    ]


async def test_llm_profile_is_tightened_and_canonicalised():
    llm = FakeLLM(
        Profile(
            target_titles=["Backend Engineer", "backend engineer", "Python Developer"],
            related_titles=["Python Developer", "Software Developer"],
            skills=["drf", "Postgres", "Python"],
            summary="Builds APIs",
        )
    )
    profile = await ProfileService(MemoryProfileRepository(), llm=llm).parse(CVS["frontend"] * 2)
    assert profile.target_titles == ["Backend Engineer", "Python Developer"]
    assert profile.related_titles == ["Software Developer"]  # no repeat of a target title
    assert profile.skills == ["Django REST Framework", "PostgreSQL", "Python"]


async def test_llm_without_related_titles_gets_them_from_role_families():
    llm = FakeLLM(Profile(target_titles=["Graphic Designer"], skills=["Canva"], summary="x"))
    profile = await ProfileService(MemoryProfileRepository(), llm=llm).parse(CVS["design"] * 2)
    assert "Brand Designer" in profile.related_titles


async def test_rebuild_all_reparses_stored_cvs_and_keeps_preferences():
    repo = MemoryProfileRepository({1: Profile(target_titles=["Old"], countries_ok=["Nigeria"])})
    repo.cv_texts.update({1: CVS["va"], 2: CVS["design"], 3: ""})
    notifier = RecordingNotifier()
    service = ProfileService(repo, notifier=notifier)
    results = await service.rebuild_all(delay_seconds=0)
    assert results == {1: "ok", 2: "ok"}
    assert "Virtual Assistant" in repo.get(1).target_titles
    assert repo.get(1).countries_ok == ["Nigeria"]  # preference kept
    assert "Profile updated" in notifier.texts_for(2)[0]
    assert "Also matching" in notifier.texts_for(2)[0]
