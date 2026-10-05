"""Role families: what kind of work someone does, independent of exact job titles.

Used to (1) suggest broader titles recruiters post, for the no-LLM parser, and
(2) pick which Remotive categories to query for the current users.
Add a family by appending to ROLE_FAMILIES.
"""

from __future__ import annotations

from dataclasses import dataclass

from jobbot.domain.text import contains_term


@dataclass(frozen=True, slots=True)
class RoleFamily:
    name: str
    triggers: tuple[str, ...]  # words in titles/skills that indicate this family
    related_titles: tuple[str, ...]  # broad titles to also search for
    remotive_categories: tuple[str, ...]


ROLE_FAMILIES: tuple[RoleFamily, ...] = (
    RoleFamily(
        "backend",
        (
            "backend",
            "back-end",
            "python",
            "django",
            "fastapi",
            "flask",
            "node.js",
            "golang",
            "java",
            "spring",
            "laravel",
            "api",
            "microservices",
        ),
        ("Backend Developer", "Python Developer", "Software Engineer", "Software Developer"),
        ("software-dev",),
    ),
    RoleFamily(
        "frontend",
        (
            "frontend",
            "front-end",
            "react",
            "next.js",
            "vue",
            "angular",
            "svelte",
            "javascript",
            "typescript",
            "html",
            "css",
            "tailwind",
        ),
        ("Frontend Developer", "React Developer", "Web Developer", "Software Developer"),
        ("software-dev",),
    ),
    RoleFamily(
        "mobile",
        ("flutter", "react native", "android", "ios", "kotlin", "swift", "mobile"),
        ("Mobile Developer", "Flutter Developer", "Software Developer"),
        ("software-dev",),
    ),
    RoleFamily(
        "data_ai",
        (
            "machine learning",
            "deep learning",
            "llm",
            "langchain",
            "nlp",
            "data scientist",
            "data analyst",
            "data engineer",
            "pandas",
            "pytorch",
            "tensorflow",
            "ai engineer",
            "power bi",
        ),
        ("AI Engineer", "Machine Learning Engineer", "Data Scientist", "Data Analyst"),
        ("data",),
    ),
    RoleFamily(
        "design",
        (
            "graphic design",
            "graphic designer",
            "designer",
            "photoshop",
            "illustrator",
            "coreldraw",
            "indesign",
            "canva",
            "figma",
            "ui/ux",
            "branding",
            "brand identity",
            "logo design",
            "motion graphics",
            "after effects",
        ),
        ("Graphic Designer", "UI/UX Designer", "Brand Designer", "Visual Designer"),
        ("design",),
    ),
    RoleFamily(
        "content",
        (
            "content creator",
            "content writer",
            "content creation",
            "copywriting",
            "copywriter",
            "social media",
            "video editing",
            "video editor",
            "tiktok",
            "youtube",
            "instagram",
            "blog",
            "seo",
            "capcut",
            "premiere pro",
            "storytelling",
        ),
        ("Content Creator", "Content Writer", "Social Media Manager", "Copywriter", "Video Editor"),
        ("writing", "marketing"),
    ),
    RoleFamily(
        "virtual_assistant",
        (
            "virtual assistant",
            "executive assistant",
            "administrative",
            "admin assistant",
            "personal assistant",
            "calendar management",
            "email management",
            "data entry",
            "customer support",
            "customer service",
            "transcription",
            "scheduling",
            "zendesk",
        ),
        (
            "Virtual Assistant",
            "Executive Assistant",
            "Administrative Assistant",
            "Customer Support Representative",
        ),
        ("customer-support", "all-others"),
    ),
)


def detect_families(titles: list[str], skills: list[str]) -> list[RoleFamily]:
    """Families whose triggers appear in the titles/skills, strongest first."""
    haystack_titles = " | ".join(titles).lower()
    haystack_skills = " | ".join(skills).lower()
    scored = []
    for family in ROLE_FAMILIES:
        score = sum(2 for t in family.triggers if contains_term(haystack_titles, t))
        score += sum(1 for t in family.triggers if contains_term(haystack_skills, t))
        if score:
            scored.append((score, family))
    scored.sort(key=lambda pair: -pair[0])
    return [family for _, family in scored]


def related_titles_for(titles: list[str], skills: list[str], limit: int = 5) -> list[str]:
    taken = {t.lower() for t in titles}
    out: list[str] = []
    for family in detect_families(titles, skills)[:2]:
        for title in family.related_titles:
            if title.lower() not in taken:
                taken.add(title.lower())
                out.append(title)
    return out[:limit]


def remotive_categories_for(titles: list[str], skills: list[str]) -> list[str]:
    out: list[str] = []
    for family in detect_families(titles, skills):
        for category in family.remotive_categories:
            if category not in out:
                out.append(category)
    return out
