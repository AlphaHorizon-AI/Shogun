"""Internal Shogun adapter module."""

from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.agent import Agent
from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.nexus import NexusTaskModel
from shogun.services.model_transport import model_chat_completion
from shogun.services.provider_credentials import provider_api_key

logger = logging.getLogger(__name__)


class InternalShogunAdapter:
    """Delegates Nexus tasks to internal Shogun agents and executes them using LLMs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_on_agent(self, task: NexusTaskModel, agent: Agent) -> dict:
        """Execute the task on the designated agent by querying its configured LLM provider."""
        logger.info("Executing task %s on agent %s", task.id, agent.name)
        
        # 1. Resolve LLM Provider
        provider = await self._resolve_provider(agent)
        if not provider:
            logger.error("No active LLM provider for task %s — cannot execute", task.id)
            return {
                "agent_name": agent.name,
                "capability": task.requested_action,
                "output": "Execution failed: No LLM provider is configured. Please add a model provider in Katana → Model Setup.",
                "status": "failed",
            }

        # 2. Formulate Prompt based on requested capability
        system_prompt = self._build_system_prompt(task, agent)
        user_message = self._build_user_message(task)

        # 3. Call LLM API
        try:
            result_text = await self._call_llm(provider, system_prompt, user_message)
            return {
                "agent_name": agent.name,
                "capability": task.requested_action,
                "output": result_text,
                "status": "success"
            }
        except Exception as exc:
            logger.error("LLM call failed for task %s: %s", task.id, exc)
            return {
                "agent_name": agent.name,
                "capability": task.requested_action,
                "output": f"Execution failed: {str(exc)}",
                "status": "failed"
            }

    async def _resolve_provider(self, agent: Agent) -> ModelProvider | None:
        """Find the configured or fallback connected model provider."""
        # 1. Check agent's bushido settings for a primary model
        bushido = agent.bushido_settings or {}
        saved_primary = bushido.get("primary_model", "")
        saved_provider_id = saved_primary.split("::")[0] if "::" in saved_primary else ""

        if saved_provider_id:
            try:
                import uuid
                res = await self.db.execute(
                    select(ModelProvider).where(ModelProvider.id == uuid.UUID(saved_provider_id))
                )
                provider = res.scalar_one_or_none()
                if provider and provider.status == "connected":
                    return provider
            except Exception:
                pass

        # 2. Fallback to any connected provider
        res = await self.db.execute(
            select(ModelProvider).where(ModelProvider.status == "connected")
        )
        return res.scalars().first()

    def _build_system_prompt(self, task: NexusTaskModel, agent: Agent) -> str:
        return f"""You are {agent.name}, acting as a specialized capability executor inside Shogun.
You have been delegated this task via the Nexus External Gateway.
Your assigned capability is: {task.requested_action}
Internal permissions granted: {', '.join(task.allowed_tools)}
Data sensitivity level: {task.data_sensitivity}

Please execute this task thoroughly and return your final response in markdown.
"""

    def _build_user_message(self, task: NexusTaskModel) -> str:
        desc = task.task_description or "No description provided."
        context = task.input_context or {}
        return f"""Task Details: {desc}
Input Context: {context}

Please process the context and provide the output for capability '{task.requested_action}'."""

    async def _call_llm(self, provider: ModelProvider, system_prompt: str, user_message: str) -> str:
        """Call the provider's /chat/completions endpoint."""
        PROVIDER_URLS = {
            "ollama":     "http://127.0.0.1:11434",
            "lmstudio":   "http://localhost:1234/v1",
            "local":      "http://localhost:1234/v1",
            "openai":     "https://api.openai.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "anthropic":  "https://api.anthropic.com/v1",
            "google":     "https://generativelanguage.googleapis.com/v1beta/openai",
        }
        
        base_url = provider.base_url or PROVIDER_URLS.get(provider.provider_type, "https://api.openai.com/v1")
        if provider.provider_type == "ollama" and not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        model_name = (
            provider.config.get("model_id")
            or (provider.config.get("models") or [None])[0]
            or provider.name
        )

        api_key = provider_api_key(provider.config)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req_json = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.3,
            "stream": False
        }

        resp = await model_chat_completion(
            auth_type=provider.auth_type,
            base_url=base_url,
            headers=headers,
            payload=req_json,
            timeout=60.0,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Model API error ({resp.status_code}): {resp.text[:300]}")

        payload = resp.json()
        return payload["choices"][0]["message"]["content"]
