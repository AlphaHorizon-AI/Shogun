"""Add offline Katana Team-panel translations to every bundled language pack."""

from __future__ import annotations

import json
from pathlib import Path

from sync_guide_translations import LANGUAGES, translate_catalog


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "frontend" / "src" / "i18n"
TEAM_STRINGS = {
    "tab": "Team",
    "title": "Team Mode",
    "description": "Only the Primary Admin uses Tenshu. Team Members communicate through Telegram or Microsoft Teams.",
    "single_user": "Single User",
    "team_mode": "Team Mode",
    "member_active_singular": "Team Member can currently be recognized through the configured channel.",
    "member_active_plural": "Team Members can currently be recognized through their configured channels.",
    "single_active": "Single-user mode is active. Saved Team Members are retained, but all of their channel access is disabled.",
    "primary_admin": "Primary Admin",
    "active": "Active",
    "disabled": "Disabled",
    "delete_member": "Delete Team Member",
    "delete_prefix": "Delete",
    "delete_suffix": "from this Shogun team? Their channel access will be revoked immediately.",
    "add_member": "Add Team Member",
    "add_button": "Add Member",
    "full_name": "Full name",
    "email_optional": "Email (optional)",
    "telegram_user_id": "Telegram user ID",
    "teams_email": "Teams sign-in email",
    "entra_id": "Entra Object ID (optional if email is set)",
    "memory_notice": "Each member receives a separate memory identity. Deleting a member revokes access and archives that member's private memory slot.",
    "loading": "Loading team configuration…",
    "unavailable": "Team configuration is unavailable.",
}


def update_pack(language: str, values: dict[str, str]) -> None:
    path = I18N / f"{language}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("katana", {})["team"] = values
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    update_pack("en", TEAM_STRINGS)
    sources = list(TEAM_STRINGS.values())
    for language in LANGUAGES:
        translated = translate_catalog(sources, language)
        update_pack(language, {key: translated[value] for key, value in TEAM_STRINGS.items()})
        print(f"{language}: Team panel complete", flush=True)


if __name__ == "__main__":
    main()
