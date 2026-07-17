"""Mappings for ALE's discovered cua-desktop and vm-primitives tools."""

from __future__ import annotations

ALE_TOOL_MAP = {
    "ronin.screen.screenshot": ("desktop", "screenshot"),
    "ronin.mouse.click": ("desktop", "click"),
    "ronin.mouse.double_click": ("desktop", "click"),
    "ronin.keyboard.type": ("desktop", "type"),
    "ronin.keyboard.hotkey": ("desktop", "key"),
    "ronin.keyboard.key_press": ("desktop", "key"),
    "ronin.mouse.scroll": ("desktop", "scroll"),
    "ronin.wait": ("desktop", "wait"),
    "sandbox.shell.run": ("vm", "run_command"),
    "sandbox.file.read": ("vm", "read_text"),
    "sandbox.file.write": ("vm", "write_text"),
    "sandbox.file.download": ("vm", "read_bytes"),
    "sandbox.file.upload": ("vm", "write_bytes"),
    "sandbox.clipboard.read": ("vm", "read_clipboard"),
    "sandbox.clipboard.write": ("vm", "write_clipboard"),
}


def normalize_arguments(tool_name: str, arguments: dict) -> dict:
    value = dict(arguments)
    if tool_name == "ronin.mouse.double_click":
        value["clicks"] = 2
    elif tool_name in {"ronin.keyboard.hotkey", "ronin.keyboard.key_press"}:
        keys = value.pop("keys", value.pop("key", []))
        value["keys"] = keys if isinstance(keys, list) else [str(keys)]
    elif tool_name == "ronin.keyboard.type":
        value = {"text": str(value.get("text", ""))}
    elif tool_name == "sandbox.shell.run" and "timeout_seconds" in value:
        value["timeout"] = value.pop("timeout_seconds")
    elif tool_name == "sandbox.file.upload":
        value["content_b64"] = value.pop("content_b64", value.pop("content", ""))
    return value
