"""Offline OCR helpers for image-only PDF pages."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


class PdfOcrError(RuntimeError):
    """Raised when no supported local OCR engine can process a PDF."""


def _run_windows_ocr_script(script: Path, arguments: list[str], timeout_seconds: int) -> dict:
    if not script.is_file():
        raise PdfOcrError(f"The bundled Windows OCR helper is missing: {script.name}")

    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(30, timeout_seconds),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PdfOcrError(f"Windows OCR could not run: {exc}") from exc

    stdout = completed.stdout.strip().lstrip("\ufeff")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        detail = completed.stderr.strip() or stdout or f"exit code {completed.returncode}"
        raise PdfOcrError(f"Windows OCR returned an invalid response: {detail[:500]}") from exc
    if completed.returncode != 0 or payload.get("status") != "success":
        raise PdfOcrError(str(payload.get("message") or "Windows OCR failed."))
    return payload


def _windows_ocr_image(path: Path, timeout_seconds: int) -> str:
    script = Path(__file__).resolve().parents[1] / "resources" / "windows_image_ocr.ps1"
    payload = _run_windows_ocr_script(
        script,
        ["-ImagePath", str(path.resolve())],
        timeout_seconds,
    )
    return str(payload.get("text") or "").strip()


def _ocr_embedded_page_images(path: Path, page_numbers: list[int], timeout_seconds: int) -> dict[int, str]:
    """Recognize raster images embedded in scanned PDF pages."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    recognized: dict[int, str] = {}
    with tempfile.TemporaryDirectory(prefix="shogun-pdf-ocr-") as temp_dir:
        temp_root = Path(temp_dir)
        for page_number in page_numbers:
            page = reader.pages[page_number - 1]
            chunks = []
            for image_index, image_file in enumerate(page.images[:10], start=1):
                image_path = temp_root / f"page-{page_number}-image-{image_index}.png"
                image_file.image.convert("RGB").save(image_path, "PNG")
                text = _windows_ocr_image(image_path, timeout_seconds)
                if text:
                    chunks.append(text)
            recognized[page_number] = "\n".join(chunks).strip()
    return recognized


def windows_ocr_pdf_pages(path: Path, page_numbers: list[int], timeout_seconds: int = 180) -> dict[int, str]:
    """Render and recognize selected PDF pages with Windows' built-in OCR engine."""
    if os.name != "nt":
        raise PdfOcrError("The built-in Windows OCR fallback is unavailable on this operating system.")
    if not page_numbers:
        return {}

    script = Path(__file__).resolve().parents[1] / "resources" / "windows_pdf_ocr.ps1"
    payload = _run_windows_ocr_script(
        script,
        [
            "-PdfPath",
            str(path.resolve()),
            "-Pages",
            ",".join(str(number) for number in page_numbers),
        ],
        timeout_seconds,
    )
    recognized = {
        int(item["page"]): str(item.get("text") or "").strip()
        for item in payload.get("pages", [])
        if item.get("page") is not None
    }
    blank_pages = [number for number in page_numbers if not recognized.get(number)]
    if blank_pages:
        embedded = _ocr_embedded_page_images(path, blank_pages, timeout_seconds)
        for page_number, text in embedded.items():
            if text:
                recognized[page_number] = text
    return recognized
