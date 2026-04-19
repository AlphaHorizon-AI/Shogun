"""i18n API — Language pack management endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from shogun.config import settings
from shogun.schemas.common import ApiResponse

router = APIRouter(prefix="/i18n", tags=["i18n"])

SETUP_JSON = Path(settings.config_path) / "setup.json"

# Available languages — must match frontend/src/i18n/*.json
LANGUAGES = [
    {"code": "en", "name": "English",    "englishName": "English",    "flag": "🇬🇧"},
    {"code": "de", "name": "Deutsch",    "englishName": "German",     "flag": "🇩🇪"},
    {"code": "it", "name": "Italiano",   "englishName": "Italian",    "flag": "🇮🇹"},
    {"code": "fr", "name": "Français",   "englishName": "French",     "flag": "🇫🇷"},
    {"code": "es", "name": "Español",    "englishName": "Spanish",    "flag": "🇪🇸"},
    {"code": "pt", "name": "Português",  "englishName": "Portuguese", "flag": "🇵🇹"},
    {"code": "pl", "name": "Polski",     "englishName": "Polish",     "flag": "🇵🇱"},
    {"code": "da", "name": "Dansk",      "englishName": "Danish",     "flag": "🇩🇰"},
    {"code": "no", "name": "Norsk",      "englishName": "Norwegian",  "flag": "🇳🇴"},
    {"code": "sv", "name": "Svenska",    "englishName": "Swedish",    "flag": "🇸🇪"},
    {"code": "uk", "name": "Українська", "englishName": "Ukrainian",  "flag": "🇺🇦"},
    {"code": "zh", "name": "中文",       "englishName": "Chinese",    "flag": "🇨🇳"},
    {"code": "ja", "name": "日本語",     "englishName": "Japanese",   "flag": "🇯🇵"},
    {"code": "ko", "name": "한국어",     "englishName": "Korean",     "flag": "🇰🇷"},
]


def _read_setup() -> dict:
    """Read the setup.json config, or return defaults."""
    if SETUP_JSON.exists():
        try:
            return json.loads(SETUP_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"language": "en", "setup_complete": False}


def _write_setup(data: dict) -> None:
    """Write setup.json config."""
    SETUP_JSON.parent.mkdir(parents=True, exist_ok=True)
    SETUP_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


@router.get("/languages", response_model=ApiResponse)
async def list_languages():
    """List all available language packs."""
    return ApiResponse(
        data=LANGUAGES,
        meta={"total": len(LANGUAGES)},
    )


@router.get("/active", response_model=ApiResponse)
async def get_active_language():
    """Return the currently active language code."""
    setup = _read_setup()
    return ApiResponse(data={"language": setup.get("language", "en")})


class LanguageBody(BaseModel):
    language: str


@router.put("/active", response_model=ApiResponse)
async def set_active_language(body: LanguageBody):
    """Set the active language."""
    valid_codes = {lang["code"] for lang in LANGUAGES}
    if body.language not in valid_codes:
        return ApiResponse(
            success=False,
            data={},
            meta={"error": f"Unknown language code: {body.language}"},
        )

    setup = _read_setup()
    setup["language"] = body.language
    _write_setup(setup)

    return ApiResponse(data={"language": body.language, "message": "Language updated."})
