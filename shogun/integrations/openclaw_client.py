"""OpenClaw College integration client.

Connects Shogun's Dojo to the OpenClawCollege.com skill catalog as the
default skill learning source. This is first-class — not a plugin.

API Reference: https://github.com/AlphaHorizon-AI/OpenClawCollege.com
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_PUBLIC_GET_ATTEMPTS = 3
_PUBLIC_GET_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_PUBLIC_GET_RETRY_DELAY_SECONDS = 0.25

# ── Constants ────────────────────────────────────────────────
OPENCLAW_BASE_URL = "https://www.openclawcollege.com/api"
OPENCLAW_API_KEY = "oc-admin-k8x9m2p4v7w1n5j3"
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
    description_md: str
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

    def _auth_header_candidates(self) -> list[dict[str, str]]:
        """Return write-auth headers in preferred fallback order.

        Existing Shogun agents may have an empty or outdated College key saved
        in their local profile. Try that profile first, then the current
        platform credential so POST operations continue to work after a key
        migration. The actor-only request is retained for College deployments
        that authorize an already verified actor without an API key.
        """
        candidates: list[dict[str, str]] = []
        seen: set[tuple[tuple[str, str], ...]] = set()

        def add(headers: dict[str, str]) -> None:
            key = tuple(sorted(headers.items()))
            if key not in seen:
                seen.add(key)
                candidates.append(headers)

        add(self._auth_headers())
        if self.api_key != OPENCLAW_API_KEY:
            add(OpenClawClient(
                base_url=self.base_url,
                timeout=self.timeout,
                actor_id=self.actor_id,
                api_key=OPENCLAW_API_KEY,
            )._auth_headers())
        if self.api_key:
            add(OpenClawClient(
                base_url=self.base_url,
                timeout=self.timeout,
                actor_id=self.actor_id,
                api_key=None,
            )._auth_headers())
        return candidates

    async def _post_authenticated(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """POST with credential fallback for authenticated College writes."""
        last_auth_error: httpx.HTTPStatusError | None = None
        for headers in self._auth_header_candidates():
            response = await self.client.post(
                f"{self.base_url}/{path.lstrip('/')}",
                json=payload,
                headers=headers,
            )
            if response.status_code in {401, 403}:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    last_auth_error = exc
                continue
            response.raise_for_status()
            return response.json()

        if last_auth_error:
            raise last_auth_error
        raise RuntimeError("OpenClaw authenticated POST failed before receiving a response")

    async def _get_authenticated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """GET a private College resource with the same credential fallback."""
        last_auth_error: httpx.HTTPStatusError | None = None
        for headers in self._auth_header_candidates():
            response = await self.client.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                headers=headers,
            )
            if response.status_code in {401, 403}:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    last_auth_error = exc
                continue
            response.raise_for_status()
            return response
        if last_auth_error:
            raise last_auth_error
        raise RuntimeError("OpenClaw authenticated GET failed before receiving a response")

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

    async def _get_public(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        allowed_statuses: frozenset[int] | None = None,
    ) -> httpx.Response:
        """GET a public College resource with bounded transient retries."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(1, _PUBLIC_GET_ATTEMPTS + 1):
            try:
                response = await self.client.get(url, params=params)
                if allowed_statuses and response.status_code in allowed_statuses:
                    return response
                if response.status_code not in _PUBLIC_GET_RETRY_STATUSES:
                    response.raise_for_status()
                    return response
                if attempt == _PUBLIC_GET_ATTEMPTS:
                    response.raise_for_status()
                failure = f"HTTP {response.status_code}"
            except httpx.RequestError as exc:
                if attempt == _PUBLIC_GET_ATTEMPTS:
                    raise
                failure = type(exc).__name__

            logger.warning(
                "OpenClaw public GET retry path=%s attempt=%d/%d failure=%s",
                path,
                attempt,
                _PUBLIC_GET_ATTEMPTS,
                failure,
            )
            await asyncio.sleep(_PUBLIC_GET_RETRY_DELAY_SECONDS * (2 ** (attempt - 1)))

        raise RuntimeError("OpenClaw public GET exhausted retries without a response")

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
        resp = await self._get_public("stats")
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
        resp = await self._get_public("categories")
        return resp.json()

    async def get_subcategories(self) -> list[dict[str, Any]]:
        """Get all subcategories grouped by faculty.

        Returns the full subcategory list matching the College UI dropdown.
        """
        resp = await self._get_public("subcategories")
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
        # The College currently returns the complete catalog, but forwarding
        # filters keeps this client ready for server-side filtering support.
        params = {
            "facultyId": faculty,
            "subcategoryId": subcategory,
            "riskTier": risk_tier,
            "search": search,
            "limit": limit,
        }
        resp = await self._get_public(
            "skills",
            params={key: value for key, value in params.items() if value is not None},
        )
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
        resp = await self._get_public(
            f"skills/{quote(skill_id, safe='')}",
            allowed_statuses=frozenset({404}),
        )
        if resp.status_code == 404:
            return None
        return self._parse_skill(resp.json())

    # ── Bundles ───────────────────────────────────────────────

    async def get_bundles(self, *, faculty: str | None = None) -> list[OpenClawBundle]:
        """Fetch all curated skill bundles."""
        resp = await self._get_public("bundles")
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
        resp = await self._get_public("specializations")
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
        public_key: str,
        private_key_pem: str | None = None,
    ) -> dict[str, Any]:
        """Register and optionally prove key possession in one handshake.

        When the private key is supplied, registration includes a fresh signed
        proof and the College certifies the agent immediately.
        """
        payload = {
            "agentName": name,
            "publicKey": public_key,
        }
        if private_key_pem:
            import secrets
            from datetime import datetime, timezone

            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding as asym_padding

            timestamp = datetime.now(timezone.utc).isoformat()
            nonce = secrets.token_hex(16)
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode("utf-8"),
                password=None,
            )
            proof = f"REGISTER{name}{timestamp}{nonce}{public_key}"
            signature = private_key.sign(
                proof.encode("utf-8"),
                asym_padding.PKCS1v15(),
                hashes.SHA256(),
            )
            payload.update({
                "timestamp": timestamp,
                "nonce": nonce,
                "signature": signature.hex(),
            })
        resp = await self.client.post(f"{self.base_url}/v1/agents/register", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def resolve_agent_id(self, membership_id: str) -> str | None:
        """Look up the internal agent ``id`` from a ``membershipId``.

        After registration, the College returns a ``membershipId`` (e.g.
        ``OCC-AGENT-HER-XXXX``).  Downstream endpoints like achievements
        and exams require the internal ``id`` (e.g. ``ag-2afee74b``).
        This method queries the agents list to resolve it.
        """
        try:
            resp = await self.client.get(f"{self.base_url}/agents")
            resp.raise_for_status()
            agents = resp.json()
            for agent in agents:
                if agent.get("membershipId") == membership_id:
                    return agent.get("id")
        except Exception as e:
            logger.warning(f"Failed to resolve agent ID for {membership_id}: {e}")
        return None

    async def verify_agent(
        self,
        membership_id: str,
        private_key_pem: str,
    ) -> dict[str, Any]:
        """Cryptographically verify agent identity with the College.

        Signs a payload with the agent's RSA private key and sends it to
        the ``/verify`` endpoint.  On success the College upgrades
        ``trustStatus`` from ``handshake_required`` to ``certified``.

        Signature payload: ``METHOD + URL_PATH + TIMESTAMP + NONCE + BODY``
        Algorithm: RSA-PKCS1v15-SHA256
        """
        import json
        import secrets
        from datetime import datetime, timezone

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding as asym_padding

        # Load private key from PEM
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=None,
        )

        timestamp = datetime.now(timezone.utc).isoformat()
        nonce = secrets.token_hex(16)
        method = "POST"
        url_path = f"/api/v1/agents/{membership_id}/verify"
        body = json.dumps({})

        # Construct and sign the payload
        sig_payload = f"{method}{url_path}{timestamp}{nonce}{body}"
        signature = private_key.sign(
            sig_payload.encode("utf-8"),
            asym_padding.PKCS1v15(),
            hashes.SHA256(),
        )

        headers = {
            "Content-Type": "application/json",
            "x-occ-membership-id": membership_id,
            "x-occ-timestamp": timestamp,
            "x-occ-nonce": nonce,
            "x-occ-signature": signature.hex(),
        }

        resp = await self.client.post(
            f"{self.base_url}/v1/agents/{membership_id}/verify",
            content=body,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Key Generation ───────────────────────────────────────

    @staticmethod
    def generate_key_pair() -> tuple[str, str]:
        """Generate an RSA-2048 key pair for College registration.

        Returns:
            (public_key_pem, private_key_pem) — both as PEM strings.
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        pub_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        return pub_pem.strip(), priv_pem.strip()

    # ── Agent Lookup ─────────────────────────────────────────

    async def get_agent_by_id(self, agent_id: str) -> dict[str, Any] | None:
        """Fetch the authenticated agent's private profile and achievements."""
        try:
            resp = await self._get_authenticated(f"v1/agents/{quote(agent_id, safe='')}/self")
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
        resp = await self._get_public("badges")
        return resp.json()

    async def enroll_specialization(
        self,
        specialization_id: str,
        agent_id: str,
    ) -> dict[str, Any]:
        """Enroll an agent and retroactively evaluate its passed exams."""
        return await self._post_authenticated(
            f"v1/specializations/{quote(specialization_id, safe='')}/enroll",
            {"agentId": agent_id},
        )

    async def evaluate_achievements(self, agent_id: str) -> dict[str, Any]:
        """Reevaluate every enrolled specialization for an agent."""
        return await self._post_authenticated(
            f"v1/agents/{quote(agent_id, safe='')}/evaluate-badges",
            {"agentId": agent_id},
        )

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
        return await self._post_authenticated("v1/feedback", payload)

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
        return await self._post_authenticated("v1/suggestions", payload)

    # ── Examination API ──────────────────────────────────────

    async def find_test(self, skill_id: str) -> dict[str, Any] | None:
        """Discover the test record for a given skill.

        GET /api/v1/tests?skillId={skillId}
        Returns test metadata (id, passThreshold) or None if not found.
        """
        resp = await self._get_authenticated("v1/tests", params={"skillId": skill_id})
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
        resp = await self._get_authenticated(f"v1/tests/{test_id}")
        resp.raise_for_status()
        return resp.json()

    async def submit_test_result(
        self,
        test_id: str,
        agent_id: str,
        score: int,
        log_artifact: str = "",
        agent_name: str | None = None,
        model_id: str | None = None,
        review: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit test results to the College.

        POST /api/v1/tests/:id/results
        If score >= passThreshold, verificationStatus will be 'approved' immediately.

        The ``agent_name`` and ``model_id`` are permanently recorded on the
        certification so it is locked to the specific agent+model that passed.
        """
        payload = {
            "agentId": agent_id,
            "score": score,
            "logArtifact": log_artifact,
        }
        if agent_name:
            payload["agentName"] = agent_name
        if model_id:
            payload["modelId"] = model_id
        if review:
            payload["review"] = review

        return await self._post_authenticated(f"v1/tests/{test_id}/results", payload)

    async def get_test_result(self, result_id: str) -> dict[str, Any] | None:
        """Check the verification status of a specific test submission.

        GET /api/v1/test-results/:id
        """
        try:
            resp = await self._get_authenticated(f"v1/test-results/{result_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch test result {result_id}: {e}")
            return None

    async def get_agent_transcript(self, agent_id: str) -> dict[str, Any] | None:
        """Fetch agent profile including full transcript and testResults.

        Uses the authenticated private self endpoint. The former generic
        ``/api/agents/:id`` route was intentionally removed when public agent
        profiles were retired.
        """
        return await self.get_agent_by_id(agent_id)

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
            description_md=version_data.get("descriptionMd", ""),
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
