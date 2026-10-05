"""Skill aliases so "DRF" matches "Django REST Framework", "PS" users match "Photoshop", etc."""

from __future__ import annotations

# canonical name -> other ways people (and job posts) write it
ALIASES: dict[str, tuple[str, ...]] = {
    # tech
    "Django REST Framework": ("DRF", "Django Rest"),
    "PostgreSQL": ("Postgres", "psql"),
    "JavaScript": ("JS", "ECMAScript"),
    "TypeScript": ("TS",),
    "React": ("React.js", "ReactJS"),
    "Next.js": ("NextJS", "Next"),
    "Vue": ("Vue.js", "VueJS"),
    "Node.js": ("Node", "NodeJS"),
    "Kubernetes": ("K8s",),
    "GCP": ("Google Cloud", "Google Cloud Platform"),
    "AWS": ("Amazon Web Services",),
    "LLM": ("LLMs", "large language model", "large language models", "GenAI", "generative AI"),
    "Machine Learning": ("ML",),
    "Golang": ("Go",),
    "CI/CD": ("continuous integration",),
    # design
    "Photoshop": ("Adobe Photoshop",),
    "Illustrator": ("Adobe Illustrator",),
    "InDesign": ("Adobe InDesign",),
    "After Effects": ("Adobe After Effects", "AE"),
    "Premiere Pro": ("Adobe Premiere", "Adobe Premiere Pro"),
    "UI/UX": ("UX/UI", "UI UX", "user experience", "product design"),
    "CorelDRAW": ("Corel Draw", "Corel"),
    # virtual assistance / admin
    "Google Workspace": ("G Suite", "GSuite", "Google Docs", "Google Sheets"),
    "Microsoft Office": ("MS Office", "Microsoft 365", "Office 365", "Excel", "Word"),
    "Calendar Management": ("scheduling", "calendar"),
    "Customer Support": ("customer service", "customer care", "customer success"),
    # content
    "Social Media Management": ("social media", "SMM", "social media marketing"),
    "Video Editing": ("video editor", "video edits"),
    "Copywriting": ("copywriter", "copy writing"),
    "Content Writing": ("content writer", "blog writing", "article writing"),
    "SEO": ("search engine optimization",),
}

_LOOKUP: dict[str, str] = {}
for canonical, aliases in ALIASES.items():
    _LOOKUP[canonical.lower()] = canonical
    for alias in aliases:
        _LOOKUP.setdefault(alias.lower(), canonical)


def canonical(skill: str) -> str:
    """'drf' -> 'Django REST Framework'. Unknown skills are returned unchanged (trimmed)."""
    return _LOOKUP.get(skill.strip().lower(), skill.strip())


def variants(skill: str) -> list[str]:
    """Every way to write a skill, canonical name first. Short aliases (<=2 chars) are only
    used when the user wrote that exact form, so "Go"/"AE"/"TS" don't match random words."""
    name = canonical(skill)
    forms = [name, *ALIASES.get(name, ())]
    if skill.strip() and skill.strip() not in forms:
        forms.append(skill.strip())
    return [f for f in forms if len(f) > 2 or f.lower() == skill.strip().lower()]
