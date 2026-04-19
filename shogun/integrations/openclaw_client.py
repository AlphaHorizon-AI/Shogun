"""OpenClaw College integration client.

Connects Shogun's Dojo to the OpenClawCollege.com skill catalog as the
default skill learning source. This is first-class — not a plugin.

API Reference: https://github.com/AlphaHorizon-AI/OpenClawCollege.com
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────
OPENCLAW_BASE_URL = "https://www.openclawcollege.com/api"
OPENCLAW_GITHUB_URL = "https://github.com/AlphaHorizon-AI/OpenClawCollege.com"
OPENCLAW_SOURCE_SLUG = "openclaw-college"
OPENCLAW_SOURCE_NAME = "OpenClaw College"


# ── Data classes for catalog entries ─────────────────────────

@dataclass
class OpenClawSkill:
    """A skill from the OpenClaw College catalog."""
    id: str
    slug: str
    name: str
    short_description: str
    faculty_id: str
    subcategory_id: str
    author_name: str
    risk_tier: str
    status: str
    version: str = "1.0.0"
    capabilities: list[str] = field(default_factory=list)
    network_access: bool = False
    filesystem_read: bool = False
    filesystem_write: bool = False
    credential_access: bool = False
    shell_execution: bool = False


@dataclass
class OpenClawBundle:
    """A curated skill bundle from OpenClaw College."""
    id: str
    name: str
    slug: str
    description: str
    faculty_id: str
    skill_count: int = 0


@dataclass
class OpenClawSpecialization:
    """A certification pathway from OpenClaw College."""
    id: str
    name: str
    slug: str
    description: str
    faculty_id: str
    badge_count: int = 0


@dataclass
class OpenClawStats:
    """Platform-wide statistics from OpenClaw College."""
    skills: int = 0
    bundles: int = 0
    specializations: int = 0
    badges: int = 0
    agents: int = 0
    categories: int = 0
    faculties: int = 0
    subcategories: int = 0


# ── Client ───────────────────────────────────────────────────

class OpenClawClient:
    """HTTP client for the OpenClaw College public API.

    Usage:
        async with OpenClawClient() as client:
            stats = await client.get_stats()
            skills = await client.search_skills(faculty="technical")
    """

    def __init__(
        self,
        base_url: str = OPENCLAW_BASE_URL,
        timeout: float = 30.0,
        actor_id: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.actor_id = actor_id
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    def _auth_headers(self) -> dict[str, str]:
        """Build authenticated headers required for exam/certification endpoints."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.actor_id:
            headers["X-Actor"] = self.actor_id
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("OpenClawClient must be used as async context manager")
        return self._client

    # ── Health ────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Check if the OpenClaw College API is reachable."""
        try:
            resp = await self.client.get(f"{self.base_url}/health")
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"OpenClaw health check failed: {e}")
            return False

    # ── Stats ─────────────────────────────────────────────────

    async def get_stats(self) -> OpenClawStats:
        """Get platform statistics."""
        resp = await self.client.get(f"{self.base_url}/stats")
        resp.raise_for_status()
        data = resp.json()
        return OpenClawStats(
            skills=data.get("skills", 0),
            bundles=data.get("bundles", 0),
            specializations=data.get("specializations", 0),
            badges=data.get("badges", 0),
            agents=data.get("agents", 0),
            categories=data.get("categories", 0),
            faculties=data.get("faculties", 0),
            subcategories=data.get("subcategories", 0),
        )

    # ── Categories ────────────────────────────────────────────

    async def get_categories(self) -> list[dict[str, Any]]:
        """Get all skill categories."""
        resp = await self.client.get(f"{self.base_url}/categories")
        resp.raise_for_status()
        return resp.json()

    async def get_subcategories(self) -> list[dict[str, Any]]:
        """Get all subcategories grouped by faculty.

        Returns the full subcategory list matching the College UI dropdown.
        """
        resp = await self.client.get(f"{self.base_url}/subcategories")
        resp.raise_for_status()
        return resp.json()

    # ── Skills ────────────────────────────────────────────────

    async def get_skills(
        self,
        *,
        faculty: str | None = None,
        subcategory: str | None = None,
        risk_tier: str | None = None,
        search: str | None = None,
        limit: int | None = None,
    ) -> list[OpenClawSkill]:
        """Fetch skills from the catalog with optional filtering.

        Because the API returns the full catalog (4000+ skills),
        filtering is done client-side for now.
        """
        resp = await self.client.get(f"{self.base_url}/skills")
        resp.raise_for_status()
        raw_skills = resp.json()

        # Client-side filtering
        if faculty:
            raw_skills = [s for s in raw_skills if s.get("facultyId") == faculty]
        if subcategory:
            raw_skills = [s for s in raw_skills if s.get("subcategoryId") == subcategory]
        if risk_tier:
            raw_skills = [s for s in raw_skills if s.get("riskTier") == risk_tier]
        if search:
            search_lower = search.lower()
            raw_skills = [
                s for s in raw_skills
                if search_lower in s.get("name", "").lower()
                or search_lower in s.get("shortDescription", "").lower()
            ]
        if limit:
            raw_skills = raw_skills[:limit]

        return [self._parse_skill(s) for s in raw_skills]

    async def get_skill_by_id(self, skill_id: str) -> OpenClawSkill | None:
        """Get a single skill by its OpenClaw ID."""
        resp = await self.client.get(f"{self.base_url}/skills/{skill_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._parse_skill(resp.json())

    # ── Bundles ───────────────────────────────────────────────

    async def get_bundles(self, *, faculty: str | None = None) -> list[OpenClawBundle]:
        """Fetch all curated skill bundles."""
        resp = await self.client.get(f"{self.base_url}/bundles")
        resp.raise_for_status()
        raw = resp.json()
        if faculty:
            raw = [b for b in raw if b.get("facultyId") == faculty]
        return [
            OpenClawBundle(
                id=b["id"],
                name=b.get("name", ""),
                slug=b.get("slug", ""),
                description=b.get("description", ""),
                faculty_id=b.get("facultyId", ""),
                skill_count=len(b.get("skillIds", [])),
            )
            for b in raw
        ]

    # ── Specializations ──────────────────────────────────────

    async def get_specializations(self) -> list[OpenClawSpecialization]:
        """Fetch all certification pathways."""
        resp = await self.client.get(f"{self.base_url}/specializations")
        resp.raise_for_status()
        raw = resp.json()
        return [
            OpenClawSpecialization(
                id=s["id"],
                name=s.get("name", ""),
                slug=s.get("slug", ""),
                description=s.get("description", ""),
                faculty_id=s.get("facultyId", ""),
                badge_count=len(s.get("requiredBadgeIds", [])),
            )
            for s in raw
        ]

    # ── Agent Registration ───────────────────────────────────

    async def register_agent(
        self,
        name: str,
        runtime: str = "shogun",
        capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register the Shogun agent with OpenClaw College.

        Returns the full registration response which includes the
        assigned ``id`` on the College platform.
        """
        payload = {
            "name": name,
            "runtime": runtime,
            "capabilities": capabilities or ["browse", "learn", "feedback"],
        }
        resp = await self.client.post(f"{self.base_url}/v1/agents/register", json=payload)
        resp.raise_for_status()
        return resp.json()

    # ── Agent Lookup ─────────────────────────────────────────

    async def get_agent_by_id(self, agent_id: str) -> dict[str, Any] | None:
        """Fetch a registered agent's profile and achievements."""
        try:
            resp = await self.client.get(f"{self.base_url}/agents/{agent_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch agent {agent_id}: {e}")
            return None

    # ── Badges ───────────────────────────────────────────────

    async def get_badges(self) -> list[dict[str, Any]]:
        """Fetch all available badges from OpenClaw College."""
        resp = await self.client.get(f"{self.base_url}/badges")
        resp.raise_for_status()
        return resp.json()

    # ── Feedback ──────────────────────────────────────────────

    async def submit_feedback(
        self,
        skill_id: str,
        agent_id: str,
        rating: int,
        comment: str = "",
    ) -> dict[str, Any]:
        """Submit skill feedback to OpenClaw College."""
        payload = {
            "skillId": skill_id,
            "agentId": agent_id,
            "rating": rating,
            "comment": comment,
        }
        resp = await self.client.post(f"{self.base_url}/v1/feedback", json=payload)
        resp.raise_for_status()
        return resp.json()

    # ── Suggestions ──────────────────────────────────────────

    async def suggest_skill(
        self,
        name: str,
        description: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Suggest a new skill to the OpenClaw College board."""
        payload = {
            "name": name,
            "description": description,
        }
        if agent_id:
            payload["agentId"] = agent_id
        resp = await self.client.post(f"{self.base_url}/v1/suggestions", json=payload)
        resp.raise_for_status()
        return resp.json()

    # ── Examination API ──────────────────────────────────────

    async def find_test(self, skill_id: str) -> dict[str, Any] | None:
        """Discover the test record for a given skill.

        GET /api/v1/tests?skillId={skillId}
        Returns test metadata (id, passThreshold) or None if not found.
        """
        resp = await self.client.get(
            f"{self.base_url}/v1/tests",
            params={"skillId": skill_id},
            headers=self._auth_headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        # API may return a list or single object
        if isinstance(data, list):
            return data[0] if data else None
        return data

    async def get_test_questions(self, test_id: str) -> dict[str, Any]:
        """Retrieve the full exam including the questions array.

        GET /api/v1/tests/:id
        Returns 30-50 MCQ questions with id, text, and options.
        """
        resp = await self.client.get(
            f"{self.base_url}/v1/tests/{test_id}",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def submit_test_result(
        self,
        test_id: str,
        agent_id: str,
        score: int,
        log_artifact: str = "",
    ) -> dict[str, Any]:
        """Submit test results to the College.

        POST /api/v1/tests/:id/results
        If score >= passThreshold, verificationStatus will be 'approved' immediately.
        """
        payload = {
            "agentId": agent_id,
            "score": score,
            "logArtifact": log_artifact,
        }
        resp = await self.client.post(
            f"{self.base_url}/v1/tests/{test_id}/results",
            json=payload,
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def get_test_result(self, result_id: str) -> dict[str, Any] | None:
        """Check the verification status of a specific test submission.

        GET /api/v1/test-results/:id
        """
        try:
            resp = await self.client.get(
                f"{self.base_url}/v1/test-results/{result_id}",
                headers=self._auth_headers(),
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch test result {result_id}: {e}")
            return None

    async def get_agent_transcript(self, agent_id: str) -> dict[str, Any] | None:
        """Fetch agent profile including full transcript and testResults.

        GET /api/agents/:id
        """
        try:
            resp = await self.client.get(
                f"{self.base_url}/agents/{agent_id}",
                headers=self._auth_headers(),
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch transcript for {agent_id}: {e}")
            return None

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _parse_skill(data: dict[str, Any]) -> OpenClawSkill:
        """Parse a raw API skill object into an OpenClawSkill."""
        version_data = data.get("currentVersion", {})
        return OpenClawSkill(
            id=data["id"],
            slug=data.get("slug", ""),
            name=data.get("name", ""),
            short_description=data.get("shortDescription", ""),
            faculty_id=data.get("facultyId", ""),
            subcategory_id=data.get("subcategoryId", ""),
            author_name=data.get("authorName", ""),
            risk_tier=data.get("riskTier", "low"),
            status=data.get("status", "unknown"),
            version=version_data.get("versionLabel", "1.0.0"),
            capabilities=version_data.get("capabilities", []),
            network_access=version_data.get("networkAccess", False),
            filesystem_read=version_data.get("filesystemRead", False),
            filesystem_write=version_data.get("filesystemWrite", False),
            credential_access=version_data.get("credentialAccess", False),
            shell_execution=version_data.get("shellExecution", False),
        )


# ── Convenience factory ──────────────────────────────────────

def get_openclaw_client(
    actor_id: str | None = None,
    api_key: str | None = None,
) -> OpenClawClient:
    """Create a new OpenClawClient instance.

    Pass actor_id and api_key to enable authenticated exam endpoints.
    """
    return OpenClawClient(actor_id=actor_id, api_key=api_key)

