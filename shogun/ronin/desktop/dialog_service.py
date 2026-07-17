"""Conservative Windows dialog classification for Ronin recovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class DialogClassification:
    detected: bool
    kind: str
    safe_to_handle: bool
    reason: str

    def model_dump(self):
        return asdict(self)


class DesktopDialogService:
    KNOWN_SAFE = {
        "save as": "save_as",
        "confirm save as": "overwrite_confirmation",
        "do you want to save": "save_confirmation",
    }
    PROTECTED = ("password", "credential", "user account control", "windows security", "payment", "bank")

    def classify(self, window: dict | None) -> DialogClassification:
        title = str((window or {}).get("title", "")).strip().lower()
        if not title:
            return DialogClassification(False, "none", False, "No active dialog")
        if any(marker in title for marker in self.PROTECTED):
            return DialogClassification(True, "protected", False, "Protected system or credential dialog")
        for marker, kind in self.KNOWN_SAFE.items():
            if marker in title:
                return DialogClassification(True, kind, True, f"Known {kind.replace('_', ' ')} dialog")
        dialog_markers = ("dialog", "warning", "confirmation", "permission", "error")
        if any(marker in title for marker in dialog_markers):
            return DialogClassification(True, "unknown", False, "Unknown dialog requires operator review")
        return DialogClassification(False, "none", False, "Active window is not classified as a dialog")


_dialog_service = DesktopDialogService()


def get_dialog_service() -> DesktopDialogService:
    return _dialog_service
