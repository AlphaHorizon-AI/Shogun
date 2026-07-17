"""Package ALE deliverables, logs, screenshots, and manifests."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

from shogun.integrations.cua import CUAMCPAdapter

from .config import write_json


class ALEArtifactExporter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        for relative in (
            "artifacts/screenshots",
            "artifacts/files",
            "artifacts/downloads",
            "artifacts/diffs",
            "artifacts/checkpoints",
            "logs",
        ):
            (output_dir / relative).mkdir(parents=True, exist_ok=True)

    async def screenshot(self, adapter: CUAMCPAdapter, name: str) -> Path:
        result = await adapter.call("ronin.screen.screenshot", {})
        image = next((item for item in result.content if item.get("type") == "image"), None)
        if not image or not image.get("data"):
            raise RuntimeError("Screenshot bridge returned no image artifact")
        path = self.output_dir / "artifacts" / "screenshots" / f"{name}.png"
        path.write_bytes(base64.b64decode(image["data"]))
        return path

    async def download(self, adapter: CUAMCPAdapter, remote_path: str) -> Path:
        result = await adapter.call("sandbox.file.download", {"path": remote_path})
        text = next((str(item.get("text", "")) for item in result.content if item.get("type") == "text"), "")
        path = self.output_dir / "artifacts" / "files" / Path(remote_path).name
        path.write_bytes(base64.b64decode(text))
        return path

    @staticmethod
    def describe(path: Path) -> dict[str, Any]:
        data = path.read_bytes()
        return {"path": str(path), "name": path.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def manifest(self, value: dict[str, Any]) -> None:
        write_json(self.output_dir / "run_manifest.json", value)

    def write_final_answer(self, text: str) -> Path:
        path = self.output_dir / "final_answer.md"
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
        return path
