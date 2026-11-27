"""Minimal system routes — local AI model discovery, Ollama helpers, notifications, and shutdown."""

from __future__ import annotations

import asyncio
import html as html_lib
import json as _json
import logging
import os
import re
import signal
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from shogun.config import settings
from shogun.db.engine import async_session_factory
from shogun.schemas.common import ApiResponse

router = APIRouter(prefix="/system", tags=["System"])
_log = logging.getLogger("shogun.system")


def _plain_html_text(value: str) -> str:
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def _parse_ollama_search_html(html: str, page: int) -> tuple[list[dict[str, Any]], bool]:
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    capabilities = {"vision", "tools", "thinking", "embedding", "cloud", "audio"}
    anchor_pattern = re.compile(
        r'<a\b[^>]*href=["\']/library/([^"\'/?#]+)["\'][^>]*>(.*?)</a>\s*</li>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in anchor_pattern.finditer(html):
        name = html_lib.unescape(match.group(1)).strip()
        if not name or name in seen:
            continue
        block = match.group(2)
        seen.add(name)
        desc_match = re.search(r'<p\b[^>]*break-words[^>]*>(.*?)</p>', block, re.IGNORECASE | re.DOTALL)
        span_texts = [
            _plain_html_text(value)
            for value in re.findall(r'<span\b[^>]*>(.*?)</span>', block, re.IGNORECASE | re.DOTALL)
        ]
        pulls_match = re.search(
            r'<span\b[^>]*>\s*([^<]+?)\s*</span>\s*<span\b[^>]*>[^<]*Pulls?',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        tags_match = re.search(
            r'<span\b[^>]*>\s*(\d+)\s*</span>\s*<span\b[^>]*>[^<]*Tags?',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        updated_match = re.search(
            r'(?:Updated(?:&nbsp;|\s)*</span>\s*)?<span\b[^>]*>\s*([^<]+?\s+ago)\s*</span>',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        sizes = [
            value
            for value in span_texts
            if re.fullmatch(r"(?:\d+(?:\.\d+)?|e\d+)b", value.lower())
        ]
        models.append(
            {
                "id": name,
                "name": name,
                "description": _plain_html_text(desc_match.group(1)) if desc_match else "",
                "sizes": list(dict.fromkeys(sizes)),
                "capabilities": list(
                    dict.fromkeys(value.lower() for value in span_texts if value.lower() in capabilities)
                ),
                "pulls": _plain_html_text(pulls_match.group(1)) if pulls_match else "0",
                "tag_count": int(tags_match.group(1)) if tags_match else 0,
                "updated": _plain_html_text(updated_match.group(1)) if updated_match else "",
            }
        )

    pagination_pages = re.findall(r'/search\?[^"\']*page=(\d+)(?:[^\d]|$)', html, re.IGNORECASE)
    has_more = str(page + 1) in pagination_pages or bool(
        re.search(r'aria-label=["\']Next Page["\']', html, re.IGNORECASE)
    )
    return models, has_more


def _local_model_destination(base_url: str, path: str):
    from shogun.services.ssrf_guard import SSRFValidationError, validate_outbound_url

    target = f"{base_url.rstrip('/')}{path}"
    try:
        return validate_outbound_url(
            target,
            policy="allowlist_only" if settings.outbound_allowlist.strip() else "loopback_only",
            allowlist=settings.outbound_allowlist,
            allow_http_on_private_network=True,
            allow_http_on_public_network=False,
        )
    except SSRFValidationError as exc:
        raise HTTPException(status_code=400, detail="Local model destination is not permitted") from exc


@router.get("/notifications", response_model=ApiResponse)
async def get_notifications(after: str | None = None):
    from shogun.services.notification_service import list_notifications

    return ApiResponse(data=list_notifications(after))


@router.post("/shutdown", response_model=ApiResponse)
async def shutdown_server():
    """Gracefully stop the local Shogun AgentFlow server."""

    async def _terminate_soon() -> None:
        await asyncio.sleep(0.25)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_terminate_soon())
    return ApiResponse(data={"shutting_down": True})


@router.get("/scan-local-models", response_model=ApiResponse)
async def scan_local_models(
    path: str = Query(..., description="Absolute path to the local model storage directory"),
):
    allowed_roots = (
        os.path.realpath(str(Path.home())),
        os.path.realpath(str(Path(__file__).resolve().parent.parent.parent.parent)),
    )
    expanded = os.path.normpath(os.path.abspath(os.path.expandvars(os.path.expanduser(path.strip()))))
    for root in allowed_roots:
        if expanded == root:
            target_dir = root
        elif expanded.startswith(root + os.sep):
            rel = expanded[len(root) + len(os.sep) :]
            target_dir = os.path.normpath(os.path.join(root, rel))
            if not target_dir.startswith(root + os.sep):
                continue
        else:
            continue

        if not os.path.isdir(target_dir):
            return ApiResponse(success=False, data=[], meta={"error": f"Path does not exist: {path}", "count": 0})

        base = Path(target_dir)
        models: list[str] = []
        for registry_root in [
            base / "manifests" / "registry.ollama.ai" / "library",
            base / "manifests" / "registry.ollama.ai" / "models",
            base / "models" / "manifests" / "registry.ollama.ai" / "library",
            base / "models" / "manifests" / "registry.ollama.ai" / "models",
        ]:
            if registry_root.exists():
                for model_dir in sorted(registry_root.iterdir()):
                    if model_dir.is_dir():
                        for tag in sorted(t.name for t in model_dir.iterdir() if t.is_file()):
                            entry = model_dir.name if tag == "latest" else f"{model_dir.name}:{tag}"
                            if entry not in models:
                                models.append(entry)

        if not models:
            for _root, _dirs, files in os.walk(target_dir):
                for fname in sorted(files):
                    if fname.lower().endswith(".gguf"):
                        name = fname[:-5]
                        if name not in models:
                            models.append(name)

        return ApiResponse(success=True, data=models, meta={"path": target_dir, "count": len(models)})

    return ApiResponse(
        success=False,
        data=[],
        meta={"error": "Model scan path must be inside your user home or project directory.", "count": 0},
    )


async def _auto_register_ollama_provider(model_name: str, base_url: str) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT id FROM model_providers WHERE name = :name AND provider_type = 'ollama'"),
            {"name": model_name},
        )
        if result.scalar_one_or_none():
            return

        new_id = str(uuid.uuid4())
        slug = model_name.replace(":", "-").replace("/", "-").replace(".", "-")
        now = datetime.now().isoformat()
        await session.execute(
            text(
                """
                INSERT INTO model_providers (
                    id, provider_type, name, slug, base_url, auth_type, is_local,
                    status, health_status, config, created_at, updated_at, created_by, updated_by
                ) VALUES (
                    :id, 'ollama', :name, :slug, :base_url, 'none', 1,
                    'connected', 'healthy', :config, :now, :now, 'system', 'system'
                )
                """
            ),
            {
                "id": new_id,
                "name": model_name,
                "slug": slug,
                "base_url": base_url,
                "config": _json.dumps({"models": [model_name]}),
                "now": now,
            },
        )
        await session.commit()


async def _sync_ollama_providers(ollama_models: list[str], base_url: str) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT id, name FROM model_providers WHERE provider_type = 'ollama'")
        )
        registered = {row[1]: row[0] for row in result.fetchall()}
        new_models = set(ollama_models) - set(registered.keys())
        for model_name in new_models:
            new_id = str(uuid.uuid4())
            slug = model_name.replace(":", "-").replace("/", "-").replace(".", "-")
            now = datetime.now().isoformat()
            await session.execute(
                text(
                    """
                    INSERT INTO model_providers (
                        id, provider_type, name, slug, base_url, auth_type, is_local,
                        status, health_status, config, created_at, updated_at, created_by, updated_by
                    ) VALUES (
                        :id, 'ollama', :name, :slug, :base_url, 'none', 1,
                        'connected', 'healthy', :config, :now, :now, 'system', 'system'
                    )
                    """
                ),
                {
                    "id": new_id,
                    "name": model_name,
                    "slug": slug,
                    "base_url": base_url,
                    "config": _json.dumps({"models": [model_name]}),
                    "now": now,
                },
            )
        if new_models:
            await session.commit()


@router.get("/pull-model")
async def pull_model_stream(
    model: str = Query(..., description="Ollama model tag, e.g. llama3.2:3b"),
    base_url: str = Query("http://127.0.0.1:11434", description="Ollama base URL"),
):
    destination = _local_model_destination(base_url, "/api/pull")

    async def event_stream():
        pull_succeeded = False
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    destination.pinned_url,
                    headers={"Host": destination.host_header},
                    extensions=destination.request_extensions,
                    json={"name": model, "stream": True},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.strip():
                            yield f"data: {line}\n\n"
                            try:
                                msg = _json.loads(line)
                                if msg.get("status") == "success":
                                    pull_succeeded = True
                            except Exception:
                                pass
        except httpx.ConnectError:
            yield f'data: {{"status":"error","error":"Cannot connect to Ollama at {base_url}. Is it running?"}}\n\n'
        except Exception:
            _log.exception("Ollama model pull failed")
            yield 'data: {"status":"error","error":"Model pull failed. Check the logs."}\n\n'
        finally:
            if pull_succeeded:
                try:
                    await _auto_register_ollama_provider(model, base_url)
                    yield f'data: {{"status":"registered","message":"Model \'{model}\' registered as provider"}}\n\n'
                except Exception as reg_exc:
                    _log.warning("Auto-register failed for %s: %s", model, reg_exc)
            yield 'data: {"status":"done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/local-models", response_model=ApiResponse)
async def get_local_models(
    provider_type: str = Query(...),
    base_url: str = Query(...),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider_type == "ollama":
                destination = _local_model_destination(base_url, "/api/tags")
                resp = await client.get(
                    destination.pinned_url,
                    headers={"Host": destination.host_header},
                    extensions=destination.request_extensions,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") or m.get("model") for m in data.get("models", [])]
                    try:
                        await _sync_ollama_providers(models, base_url)
                    except Exception:
                        pass
                    return ApiResponse(success=True, data=models)
                return ApiResponse(
                    success=False,
                    data=[],
                    meta={"error": f"Ollama returned {resp.status_code}: {resp.text[:200]}"},
                )

            destination = _local_model_destination(base_url, "/models")
            resp = await client.get(
                destination.pinned_url,
                headers={"Host": destination.host_header},
                extensions=destination.request_extensions,
            )
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", [])]
                return ApiResponse(success=True, data=models)
            return ApiResponse(
                success=False,
                data=[],
                meta={"error": f"Local provider returned {resp.status_code}: {resp.text[:200]}"},
            )
    except httpx.ConnectError:
        return ApiResponse(
            success=False,
            data=[],
            meta={"error": f"Cannot connect to provider at {base_url}. Is it running?"},
        )
    except Exception:
        _log.exception("Local model scan failed")
        return ApiResponse(success=False, data=[], meta={"error": "Local model scan failed."})


@router.get("/ollama-search", response_model=ApiResponse)
async def search_ollama_models(
    q: str = Query(""),
    p: int = Query(1, ge=1),
    c: str = Query(""),
):
    params: dict[str, str] = {}
    if q.strip():
        params["q"] = q.strip()
    if p > 1:
        params["page"] = str(p)
    if c.strip():
        params["c"] = c.strip()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://ollama.com/search",
                params=params,
                headers={"User-Agent": "Shogun/1.0 (model-search)"},
            )
            if resp.status_code != 200:
                return ApiResponse(success=False, data=[], meta={"error": f"Ollama returned {resp.status_code}"})
            models, has_more = _parse_ollama_search_html(resp.text, p)
            return ApiResponse(success=True, data={"models": models, "page": p, "has_more": has_more, "query": q})
    except httpx.ConnectError:
        return ApiResponse(success=False, data=[], meta={"error": "Cannot connect to ollama.com."})
    except Exception:
        _log.exception("Ollama registry search failed")
        return ApiResponse(success=False, data=[], meta={"error": "Ollama registry search failed."})


@router.delete("/delete-model")
async def delete_ollama_model(
    model: str = Query(...),
    base_url: str = Query("http://127.0.0.1:11434"),
):
    try:
        destination = _local_model_destination(base_url, "/api/delete")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                "DELETE",
                destination.pinned_url,
                headers={"Host": destination.host_header},
                extensions=destination.request_extensions,
                json={"name": model},
            )
            if resp.status_code == 200:
                try:
                    async with async_session_factory() as session:
                        await session.execute(
                            text("DELETE FROM model_providers WHERE name = :name AND provider_type = 'ollama'"),
                            {"name": model},
                        )
                        await session.commit()
                except Exception:
                    pass
                return {"success": True, "message": f"Model '{model}' deleted and deregistered."}
            return {"success": False, "message": f"Ollama returned {resp.status_code}: {resp.text[:300]}"}
    except httpx.ConnectError:
        return {"success": False, "message": f"Cannot connect to Ollama at {base_url}. Is it running?"}
    except Exception:
        _log.exception("Ollama model deletion failed")
        return {"success": False, "message": "Model deletion failed."}
