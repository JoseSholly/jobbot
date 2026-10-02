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

CV_PROMPT = """You extract a job-search profile from a CV. Return ONLY JSON with these keys:
- "target_titles": 3-6 job titles this person should search for (based on experience), strings
- "skills": up to 25 concrete skills/tools/technologies, most important first
- "seniority": subset of ["intern","junior","mid","senior","lead"] that fits
- "exclude_keywords": words that signal a bad fit (e.g. "unpaid", "internship" for experienced people)
- "summary": 2-4 sentence third-person summary of experience and strengths (used for semantic matching)

CV:
\"\"\"
{cv}
\"\"\""""

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

    async def generate_json(self, prompt: str, temperature: float = 0.2):
        resp = await request(
            self.client,
            "POST",
            f"{API}/{self.model}:generateContent",
            headers={"x-goog-api-key": self.api_key},
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": temperature},
            },
        )
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)

    async def parse_cv(self, cv_text: str) -> Profile | None:
        data = await self.generate_json(CV_PROMPT.format(cv=cv_text[:15000]))
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
