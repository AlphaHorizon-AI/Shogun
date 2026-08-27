"""Secure model-catalog discovery for cloud and OpenAI-compatible providers."""

from __future__ import annotations

from typing import Any

import httpx

from shogun.services.ssrf_guard import SSRFValidationError, validate_outbound_url

_MAX_CATALOG_BYTES = 5 * 1024 * 1024


class ModelDiscoveryError(RuntimeError):
    """A provider catalog could not be retrieved or parsed safely."""


def _catalog_headers(provider_type: str, api_key: str | None, project_id: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if not api_key:
        return headers
    if provider_type == "anthropic":
        headers.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    if provider_type == "google" and project_id:
        headers["x-goog-user-project"] = project_id
    return headers


def _parse_catalog(provider_type: str, payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    records = payload.get("data")
    if not isinstance(records, list):
        records = payload.get("models")
    if not isinstance(records, list):
        return []

    models: list[str] = []
    for record in records[:10_000]:
        if isinstance(record, str):
            model_id = record
        elif isinstance(record, dict):
            model_id = record.get("id") or record.get("name") or record.get("model")
        else:
            continue
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        model_id = model_id.strip()
        if provider_type == "google" and model_id.startswith("models/"):
            model_id = model_id.removeprefix("models/")
        if model_id not in models:
            models.append(model_id)
    return sorted(models, key=str.casefold)


async def discover_provider_models(
    *,
    provider_type: str,
    base_url: str,
    api_key: str | None,
    project_id: str | None = None,
) -> list[str]:
    """Fetch a provider's model list without allowing redirects or private-network pivots."""

    catalog_url = f"{base_url.rstrip('/')}/models"
    try:
        destination = validate_outbound_url(
            catalog_url,
            policy="public_only",
            allow_http_on_private_network=False,
            allow_http_on_public_network=False,
            allowed_ports=(443,),
        )
    except SSRFValidationError as exc:
        raise ModelDiscoveryError("The provider model-catalog destination is not permitted.") from exc

    headers = _catalog_headers(provider_type, api_key, project_id)
    headers["Host"] = destination.host_header
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            response = await client.get(
                destination.pinned_url,
                headers=headers,
                extensions=destination.request_extensions,
            )
    except httpx.HTTPError as exc:
        raise ModelDiscoveryError("Could not connect to the provider model catalog.") from exc

    if response.status_code in {401, 403}:
        raise ModelDiscoveryError("The provider rejected the credential used for model discovery.")
    if response.status_code >= 400:
        raise ModelDiscoveryError(f"The provider model catalog returned HTTP {response.status_code}.")
    if len(response.content) > _MAX_CATALOG_BYTES:
        raise ModelDiscoveryError("The provider model catalog response was too large.")
    try:
        models = _parse_catalog(provider_type, response.json())
    except ValueError as exc:
        raise ModelDiscoveryError("The provider returned an invalid model catalog.") from exc
    if not models:
        raise ModelDiscoveryError("The provider returned no selectable models.")
    return models
