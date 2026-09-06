"""Translate Shogun chat requests and SSE events to the subscription Responses backend."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import httpx

from shogun.services.openai_oauth import RESPONSES_URL
from shogun.services.provider_oauth import ProviderOAuthError


def responses_payload(payload: dict) -> dict:
    instructions, items = [], []
    for message in payload.get("messages", []):
        role, content = message.get("role", "user"), message.get("content")
        if role in {"system", "developer"}:
            instructions.append(content if isinstance(content, str) else json.dumps(content))
            continue
        if role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": message["tool_call_id"],
                    "output": content if isinstance(content, str) else json.dumps(content),
                }
            )
            continue
        parts = []
        if isinstance(content, str) and content:
            parts = [{"type": "output_text" if role == "assistant" else "input_text", "text": content}]
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    parts.append({"type": "output_text" if role == "assistant" else "input_text", "text": part["text"]})
                elif part.get("type") == "image_url" and role == "user":
                    image = part["image_url"]
                    parts.append(
                        {"type": "input_image", "image_url": image["url"], "detail": image.get("detail", "auto")}
                    )
                else:
                    raise ProviderOAuthError("This message content type is not supported by ChatGPT OAuth.")
        if parts:
            items.append({"type": "message", "role": role, "content": parts})
        for call in message.get("tool_calls") or []:
            function = call["function"]
            items.append(
                {
                    "type": "function_call",
                    "call_id": call["id"],
                    "name": function["name"],
                    "arguments": function["arguments"],
                }
            )
    tools = []
    for tool in payload.get("tools") or []:
        if tool.get("type") != "function":
            raise ProviderOAuthError("This tool type is not supported by ChatGPT OAuth.")
        tools.append({"type": "function", **tool["function"]})
    result = {
        "model": payload["model"],
        "stream": True,
        "store": False,
        "instructions": "\n\n".join(instructions) or "You are Shogun's assistant.",
        "input": items,
        "tools": tools,
        "parallel_tool_calls": payload.get("parallel_tool_calls", False),
    }
    choice = payload.get("tool_choice")
    if choice is not None:
        result["tool_choice"] = (
            {"type": "function", "name": choice["function"]["name"]} if isinstance(choice, dict) else choice
        )
    if payload.get("reasoning_effort"):
        result["reasoning"] = {"effort": payload["reasoning_effort"]}
    response_format = payload.get("response_format") or {}
    if response_format.get("type") == "json_schema":
        result["text"] = {"format": {"type": "json_schema", **response_format["json_schema"]}}
    elif response_format.get("type") == "json_object":
        result["instructions"] += "\nReturn one valid JSON object, without Markdown fences."
    return result


class ChatGPTStream:
    def __init__(self, response):
        self.response = response
        self.status_code = response.status_code

    async def aread(self):
        # Provider responses can contain sensitive account/request details.
        return json.dumps(
            {
                "error": {
                    "message": (
                        f"ChatGPT request failed (HTTP {self.status_code}). "
                        "Check sign-in and subscription limits."
                    )
                }
            }
        ).encode()

    async def aiter_lines(self):
        completed = False
        call_indices = {}
        async for line in self.response.aiter_lines():
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            try:
                event = json.loads(line[5:].strip())
                if not isinstance(event, dict):
                    raise ValueError
            except ValueError:
                raise ProviderOAuthError("ChatGPT returned an invalid stream event.") from None
            kind, delta = event.get("type"), {}
            if kind in {"response.failed", "response.incomplete", "error"}:
                raise ProviderOAuthError(
                    "ChatGPT could not finish this response. Check model access and subscription limits."
                )
            if kind in {"response.output_text.delta", "response.refusal.delta"}:
                delta = {"content": event.get("delta", "")}
            elif kind == "response.output_item.added" and (event.get("item") or {}).get("type") == "function_call":
                item = event["item"]
                index = len(call_indices)
                call_indices[event["output_index"]] = index
                delta = {
                    "tool_calls": [
                        {
                            "index": index,
                            "id": item["call_id"],
                            "type": "function",
                            "function": {"name": item["name"], "arguments": ""},
                        }
                    ]
                }
            elif kind == "response.function_call_arguments.delta":
                output_index = event.get("output_index")
                if output_index not in call_indices:
                    raise ProviderOAuthError("ChatGPT returned an incomplete tool call.")
                delta = {
                    "tool_calls": [
                        {"index": call_indices[output_index], "function": {"arguments": event.get("delta", "")}}
                    ]
                }
            elif kind == "response.completed":
                completed = True
                usage = (event.get("response") or {}).get("usage") or {}
                yield "data: " + json.dumps(
                    {
                        "choices": [
                            {"index": 0, "delta": {}, "finish_reason": "tool_calls" if call_indices else "stop"}
                        ],
                        "usage": {
                            "prompt_tokens": usage.get("input_tokens", 0),
                            "completion_tokens": usage.get("output_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                        },
                    }
                )
            if delta:
                yield "data: " + json.dumps({"choices": [{"index": 0, "delta": delta, "finish_reason": None}]})
        if not completed:
            raise ProviderOAuthError("ChatGPT stream ended before completion. Try again.")
        yield "data: [DONE]"


@asynccontextmanager
async def subscription_stream(headers: dict, payload: dict, timeout: float):
    if not headers.get("ChatGPT-Account-ID") or not headers.get("Authorization"):
        raise ProviderOAuthError("ChatGPT is disconnected. Reconnect in The Katana.")
    # Never send subscription credentials to a configurable Platform/base URL.
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        async with client.stream(
            "POST",
            RESPONSES_URL,
            headers={
                "Authorization": headers["Authorization"],
                "ChatGPT-Account-ID": headers["ChatGPT-Account-ID"],
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "OpenAI-Beta": "responses=v1",
                "originator": "shogun",
            },
            json=responses_payload(payload),
        ) as response:
            yield ChatGPTStream(response)


async def subscription_completion(headers: dict, payload: dict, timeout: float):
    from shogun.services.model_transport import ModelTransportResponse

    content, calls, usage = "", {}, {}
    async with subscription_stream(headers, payload, timeout) as response:
        if response.status_code != 200:
            return ModelTransportResponse(response.status_code, (await response.aread()).decode())
        async for line in response.aiter_lines():
            if line == "data: [DONE]":
                break
            chunk = json.loads(line[5:])
            usage = chunk.get("usage", usage)
            delta = chunk["choices"][0]["delta"]
            content += delta.get("content", "")
            for call in delta.get("tool_calls") or []:
                target = calls.setdefault(
                    call["index"], {"id": call.get("id"), "type": "function", "function": {"name": "", "arguments": ""}}
                )
                target["function"]["name"] += call["function"].get("name", "")
                target["function"]["arguments"] += call["function"].get("arguments", "")
    message = {"role": "assistant", "content": content or None}
    if calls:
        message["tool_calls"] = list(calls.values())
    return ModelTransportResponse(
        200,
        json.dumps(
            {
                "model": payload["model"],
                "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if calls else "stop"}],
                "usage": usage,
            }
        ),
    )
