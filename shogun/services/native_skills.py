"""Native Skills — Internal system capabilities exposed directly to the Shogun orchestrator LLM."""

import json
import logging
from typing import Any

from shogun.db.engine import async_session_factory
from shogun.api.agents import _get_system_context

logger = logging.getLogger("shogun.native_skills")

NATIVE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "spawn_samurai",
            "description": "Spawn a new Samurai agent in the Dojo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the Samurai agent.",
                    },
                    "role": {
                        "type": "string",
                        "description": "The specific role or designation.",
                    },
                    "persona": {
                        "type": "string",
                        "description": "A brief description of their personality and expertise.",
                    },
                    "security_tier": {
                        "type": "string",
                        "enum": ["shrine", "guarded", "tactical", "campaign", "ronin"],
                        "description": "Security tier for the new Samurai (typically tactical or guarded).",
                    },
                },
                "required": ["name", "role", "persona", "security_tier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_available_models",
            "description": "List all active model providers and the models they have available.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_model_settings",
            "description": "Update Shogun's primary and fallback models. Use when the user requests to switch the core model.",
            "parameters": {
                "type": "object",
                "properties": {
                    "primary_model": {
                        "type": "string",
                        "description": "The fully qualified primary model string (e.g. 'provider-id::model-name'). Use list_available_models if unsure.",
                    },
                    "fallback_models": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of fully qualified models to fall back to.",
                    },
                },
                "required": ["primary_model"],
            },
        },
    },
]

async def execute_native_tool(name: str, args: dict[str, Any], db_session) -> str:
    """Route tool execution from LLM to underlying services."""
    logger.info(f"Executing native skill: {name} with args {args}")
    
    try:
        if name == "spawn_samurai":
            from shogun.services.agent_service import AgentService
            svc = AgentService(db_session)
            # Create the agent via service directly
            await svc.create(
                agent_type="samurai",
                name=args["name"],
                slug=args["name"].lower().replace(" ", "-"),
                description=f"{args['role']} - {args['persona']}",
                status="active",
                spawn_policy="manual" # Or derived...
            )
            # Update cache context so next stream shows +1 agent
            import time
            from shogun.api.agents import _CTX_CACHE
            _CTX_CACHE["ts"] = 0 
            
            await db_session.commit()
            
            return json.dumps({
                "status": "success", 
                "message": f"Samurai '{args['name']}' successfully spawned at tier '{args['security_tier']}'."
            })
            
        elif name == "list_available_models":
            from sqlalchemy import select
            from shogun.db.models.model_provider import ModelProvider
            
            providers = await db_session.execute(
                select(ModelProvider).where(ModelProvider.status == "connected")
            )
            
            res = {}
            for p in providers.scalars().all():
                models = p.config.get("models", [])
                if p.config.get("model_id"):
                    models.append(p.config.get("model_id"))
                res[f"{p.name} (UUID: {p.id})"] = models
                
            return json.dumps({
                "status": "success",
                "available_providers_and_models": res
            })
            
        elif name == "update_model_settings":
            from shogun.db.models.agent import Agent
            from sqlalchemy import select
            
            shogun_res = await db_session.execute(
                select(Agent).where(
                    Agent.agent_type == "shogun",
                    Agent.is_primary == True,
                    Agent.is_deleted == False
                ).limit(1)
            )
            shogun = shogun_res.scalar_one_or_none()
            if not shogun:
                return json.dumps({"status": "error", "message": "Primary Shogun not found."})
                
            bushido = dict(shogun.bushido_settings) if shogun.bushido_settings else {}
            bushido["primary_model"] = args["primary_model"]
            if "fallback_models" in args:
                bushido["fallback_models"] = args["fallback_models"]
                
            shogun.bushido_settings = bushido
            db_session.add(shogun)
            await db_session.commit()
            
            return json.dumps({
                "status": "success", 
                "message": f"Successfully updated primary model to {args['primary_model']}."
            })
            
        else:
            return json.dumps({"status": "error", "message": f"Unknown tool: {name}"})
            
    except Exception as e:
        logger.error(f"Native skill execution failed: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})
