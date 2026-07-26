"""Single-source Comms permissions resolved from the active ToolGate posture."""

from __future__ import annotations

from fastapi import HTTPException


async def effective_account_permissions() -> dict[str, bool]:
    """Expose ToolGate Comms capabilities using the legacy account field names."""
    from shogun.api.security import _get_agent_posture

    posture = await _get_agent_posture()
    read_mail = bool(posture.get("comms_read_email", True))
    write_mail = bool(posture.get("comms_send_email", True))
    read_calendar = bool(posture.get("comms_read_calendar", True))
    write_calendar = bool(posture.get("comms_create_events", True))
    return {
        "perm_read_mail": read_mail,
        "perm_send_mail": write_mail,
        "perm_delete_mail": write_mail,
        "perm_read_calendar": read_calendar,
        "perm_create_events": write_calendar,
        "perm_edit_events": write_calendar,
        "perm_delete_events": write_calendar,
    }


async def require_comms_permission(permission: str) -> None:
    permissions = await effective_account_permissions()
    if not permissions.get(permission, False):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied by ToolGate Comms policy: {permission}",
        )
