"""Gemini (Google AI Studio free tier) via REST. Implements interfaces.ml.LLMClient."""

from __future__ import annotations

import json
import logging

import httpx

from jobbot.adapters.http import request
from jobbot.domain.models import Job, Profile
from jobbot.domain.text import truncate

log = logging.getLogger(__name__)

API = "https://generativelanguage.googleapis.com/v1beta/models"

CV_PROMPT = (
    "You extract a tight job-search profile from a CV. The person may work in ANY field: "
    "software, design, content creation, virtual assistance, marketing, admin, and so on. "
    "Fill these fields:\n"
    "- target_titles: 3-4 canonical job titles this person should search for. "
    'No near-duplicates (do not list both "Backend Engineer" and "Senior Backend Engineer" '
    "— pick one). Prefer titles recruiters actually post.\n"
    "- related_titles: 3-6 broader or adjacent titles that job boards (including Nigerian boards "
    "like MyJobMag and Jobberman) commonly use for the same work, not repeating target_titles. "
    'E.g. a Django engineer -> "Python Developer", "Backend Developer", "Software Developer"; '
    'a social media creator -> "Content Creator", "Social Media Manager", "Copywriter"; '
    'an assistant -> "Virtual Assistant", "Executive Assistant", "Administrative Assistant".\n'
    "- skills: up to 12 core hard skills, tools and software of THEIR field, most important first. "
    "Developers: languages, frameworks, databases, cloud, major integrations. "
    "Designers: e.g. Figma, Photoshop, Illustrator, Canva, CorelDRAW, branding. "
    "Content creators: e.g. copywriting, video editing, CapCut, SEO, social media management. "
    "Virtual assistants: e.g. Google Workspace, Microsoft Office, calendar/email management, "
    "CRM tools, data entry. "
    "EXCLUDE soft skills (communication, teamwork), and for developers: test frameworks "
    "(pytest, jest), linters/formatters (ruff, prettier, black), CI/CD, deployment platforms "
    "(Railway, Vercel, Heroku, Fly), auth protocol names (JWT, OAuth2), and abstract concepts "
    "(idempotency, database optimization, REST API design, scalability).\n"
    '- seniority: subset of ["intern","junior","mid","senior","lead"] that fits\n'
    "- domains: 0-4 industries they have worked in (e.g. fintech, e-commerce, healthtech, "
    "media, education)\n"
    "- exclude_keywords: words that signal a bad fit "
    '(e.g. "unpaid", "internship" for experienced people)\n'
    "- summary: 1-2 sentence third-person summary of experience and strengths, "
    "max 300 characters (used for semantic matching)\n"
    "\n"
    "CV:\n"
    '"""\n'
    "{cv}\n"
    '"""'
)

_STRINGS = {"type": "ARRAY", "items": {"type": "STRING"}}
CV_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "target_titles": _STRINGS,
        "related_titles": _STRINGS,
        "skills": _STRINGS,
        "seniority": {
            "type": "ARRAY",
            "items": {"type": "STRING", "enum": ["intern", "junior", "mid", "senior", "lead"]},
        },
        "domains": _STRINGS,
        "exclude_keywords": _STRINGS,
        "summary": {"type": "STRING"},
    },
    "required": ["target_titles", "related_titles", "skills", "seniority", "summary"],
    "propertyOrdering": [
        "target_titles",
        "related_titles",
        "skills",
        "seniority",
        "domains",
        "exclude_keywords",
        "summary",
    ],
}

REASONS_PROMPT = """Candidate profile:
{profile}

For each job below, write ONE short sentence (max 18 words) on why it matches this candidate,
citing concrete overlaps. Return ONLY a JSON array of strings, same order, same length ({n}).

Jobs:
{jobs}"""


class GeminiClient:
    def __init__(self, api_key: str, client: httpx.AsyncClient, model: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self.api_key = api_key
        self.client = client
        self.model = model

    async def generate_json(self, prompt: str, temperature: float = 0.2, schema: dict | None = None):
        resp = await request(
            self.client,
            "POST",
            f"{API}/{self.model}:generateContent",
            headers={"x-goog-api-key": self.api_key},
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": temperature,
                    **({"responseSchema": schema} if schema else {}),
                },
            },
        )
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)

    async def parse_cv(self, cv_text: str) -> Profile | None:
        data = await self.generate_json(
            CV_PROMPT.format(cv=cv_text[:15000]), temperature=0.0, schema=CV_SCHEMA
        )
        if not isinstance(data, dict):
            return None
        return Profile.from_dict(data)

    async def match_reasons(self, profile: Profile, jobs: list[Job]) -> list[str] | None:
        listing = "\n".join(
            f"{i}. {job.title} at {job.company}: {truncate(job.description, 500)}"
            for i, job in enumerate(jobs, start=1)
        )
        data = await self.generate_json(
            REASONS_PROMPT.format(profile=truncate(profile.embedding_text, 1500), jobs=listing, n=len(jobs))
        )
        if isinstance(data, list) and len(data) == len(jobs):
            return [str(x).strip() for x in data]
        log.warning("match_reasons returned unexpected shape")
        return None
