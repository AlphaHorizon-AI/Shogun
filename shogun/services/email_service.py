"""Lightweight SMTP/IMAP email service for AgentFlow email nodes.

Reads optional SMTP_* and IMAP_* environment variables from .env.
"""

from __future__ import annotations

import asyncio
import imaplib
import os
import smtplib
from email import message_from_bytes
from email.message import EmailMessage
from typing import Any


class EmailService:
    def __init__(self, session: Any = None) -> None:
        self.session = session

    async def get_account(self) -> dict[str, Any] | None:
        host = os.environ.get("SMTP_HOST", "").strip()
        user = os.environ.get("SMTP_USER", "").strip()
        if not host:
            return None
        return {
            "smtp_host": host,
            "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
            "smtp_user": user,
            "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
            "from_address": os.environ.get("SMTP_FROM", user or "shogun@localhost"),
            "imap_host": os.environ.get("IMAP_HOST", host),
            "imap_port": int(os.environ.get("IMAP_PORT", "993")),
        }

    async def send_email(self, compose: Any) -> dict[str, Any]:
        acc = await self.get_account()
        if not acc:
            raise ValueError(
                "No SMTP account configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD in .env."
            )

        def _send() -> None:
            msg = EmailMessage()
            msg["From"] = acc["from_address"]
            msg["To"] = compose.to_address
            if getattr(compose, "cc_address", None):
                msg["Cc"] = compose.cc_address
            msg["Subject"] = compose.subject
            msg.set_content(compose.body or "")
            with smtplib.SMTP(acc["smtp_host"], acc["smtp_port"], timeout=20) as server:
                try:
                    server.starttls()
                except Exception:
                    pass
                if acc["smtp_user"]:
                    server.login(acc["smtp_user"], acc["smtp_password"])
                server.send_message(msg)

        await asyncio.to_thread(_send)
        return {"status": "sent", "message": "Email sent via SMTP"}

    async def list_messages(
        self,
        folder: str = "INBOX",
        page: int = 1,
        per_page: int = 10,
        unread_only: bool = True,
    ) -> list[dict[str, Any]]:
        acc = await self.get_account()
        if not acc or not acc.get("imap_host"):
            raise ValueError(
                "No IMAP account configured. Set IMAP_HOST, SMTP_USER, and SMTP_PASSWORD in .env."
            )

        def _fetch() -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
            with imaplib.IMAP4_SSL(acc["imap_host"], acc["imap_port"]) as client:
                client.login(acc["smtp_user"], acc["smtp_password"])
                client.select(folder, readonly=True)
                criteria = "UNSEEN" if unread_only else "ALL"
                _status, data = client.search(None, criteria)
                ids = (data[0].split() if data and data[0] else [])[::-1]
                start = max(0, (page - 1) * per_page)
                for msg_id in ids[start : start + per_page]:
                    _st, msg_data = client.fetch(msg_id, "(RFC822.HEADER)")
                    if not msg_data or not isinstance(msg_data[0], tuple):
                        continue
                    parsed = message_from_bytes(msg_data[0][1])
                    items.append(
                        {
                            "id": msg_id.decode("utf-8", errors="ignore"),
                            "from": parsed.get("From", ""),
                            "subject": parsed.get("Subject", ""),
                            "date": parsed.get("Date", ""),
                        }
                    )
            return items

        return await asyncio.to_thread(_fetch)
