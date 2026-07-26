"""Email service for IMAP/POP3 reading and SMTP sending."""

from __future__ import annotations

import asyncio
import base64
import email
import hashlib
import imaplib
import re
import smtplib
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.email_account import EmailAccount
from shogun.schemas.channels import EmailAccountCreate, EmailAccountUpdate, EmailComposeRequest
from shogun.services.base_service import BaseService
from shogun.services.comms_permissions import require_comms_permission


def _get_fernet(key: str | None = None) -> Fernet:
    """Derive a 32-byte URL-safe base64 key from settings.vault_encryption_key."""
    key_bytes = (key or settings.vault_encryption_key).encode("utf-8")
    hashed = hashlib.sha256(key_bytes).digest()
    fernet_key = base64.urlsafe_b64encode(hashed)
    return Fernet(fernet_key)


def encrypt_password(password: str) -> str:
    f = _get_fernet()
    return f.encrypt(password.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted: str) -> str:
    payload = encrypted.encode("utf-8")
    try:
        return _get_fernet().decrypt(payload).decode("utf-8")
    except InvalidToken:
        # Keep credentials created by older desktop installers readable after
        # replacing the historical placeholder vault key on upgrade.
        legacy_key = "change-me-to-a-fernet-base64-key"
        if settings.vault_encryption_key == legacy_key:
            raise
        return _get_fernet(legacy_key).decrypt(payload).decode("utf-8")


def parse_header_str(header_value: str | None) -> str:
    if not header_value:
        return ""
    try:
        decoded = decode_header(header_value)
        parts = []
        for val, charset in decoded:
            if isinstance(val, bytes):
                charset = charset or "utf-8"
                try:
                    parts.append(val.decode(charset, errors="replace"))
                except Exception:
                    parts.append(val.decode("utf-8", errors="replace"))
            else:
                parts.append(str(val))
        return "".join(parts)
    except Exception:
        return str(header_value)


def _decode_imap_utf7(value: str) -> str:
    """Decode IMAP modified UTF-7 folder names, leaving plain ASCII intact."""
    if "&" not in value:
        return value

    out: list[str] = []
    i = 0
    while i < len(value):
        if value[i] != "&":
            out.append(value[i])
            i += 1
            continue

        end = value.find("-", i)
        if end == -1:
            out.append(value[i:])
            break

        token = value[i + 1:end]
        if token == "":
            out.append("&")
        else:
            try:
                padded = token.replace(",", "/")
                padded += "=" * ((4 - len(padded) % 4) % 4)
                out.append(base64.b64decode(padded).decode("utf-16-be"))
            except Exception:
                out.append(value[i:end + 1])
        i = end + 1

    return "".join(out)


def _unquote_imap_name(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1].replace(r"\"", '"').replace(r"\\", "\\")
    return _decode_imap_utf7(value)


def _parse_imap_list_line(line: bytes | str) -> str | None:
    """Extract a selectable mailbox name from an IMAP LIST response line."""
    text = line.decode("utf-8", errors="ignore") if isinstance(line, bytes) else str(line)
    match = re.match(r'\((?P<flags>.*?)\)\s+(?P<delimiter>"[^"]*"|NIL)\s+(?P<name>.+)$', text)
    if match:
        return _unquote_imap_name(match.group("name"))

    # Fallback for unusual servers: the mailbox is normally the final token.
    parts = text.rsplit(" ", 1)
    if parts:
        return _unquote_imap_name(parts[-1])
    return None


def _quote_mailbox(folder: str) -> str:
    if folder.upper() == "INBOX":
        return "INBOX"
    escaped = folder.replace("\\", "\\\\").replace('"', r"\"")
    return f'"{escaped}"'


def _folder_candidates(folder: str) -> list[str]:
    lname = folder.lower()
    aliases = {
        "sent": ["Sent", "Sent Mail", "[Gmail]/Sent Mail", "[Google Mail]/Sent Mail"],
        "drafts": ["Drafts", "[Gmail]/Drafts", "[Google Mail]/Drafts"],
        "trash": ["Trash", "Bin", "[Gmail]/Trash", "[Gmail]/Bin", "[Google Mail]/Trash", "[Google Mail]/Bin"],
        "archive": ["Archive", "All Mail", "[Gmail]/All Mail", "[Google Mail]/All Mail"],
        "all mail": ["All Mail", "[Gmail]/All Mail", "[Google Mail]/All Mail"],
    }
    candidates = [folder]
    for key, values in aliases.items():
        if lname == key or key in lname:
            candidates.extend(values)
    return list(dict.fromkeys(candidates))


def _select_mailbox(mail: imaplib.IMAP4, folder: str):
    last_status = None
    last_data = None
    for candidate in _folder_candidates(folder):
        status, data = mail.select(_quote_mailbox(candidate))
        last_status, last_data = status, data
        if status == "OK":
            return status, data
    return last_status, last_data


class EmailService(BaseService[EmailAccount]):
    """Handle mail operations governed by ToolGate's Comms policy."""

    def __init__(self, session: AsyncSession):
        super().__init__(EmailAccount, session)

    async def get_account(self) -> EmailAccount | None:
        """Fetch the single email account configuration."""
        result = await self.session.execute(select(self.model).limit(1))
        return result.scalars().first()

    async def configure_account(self, data: EmailAccountCreate) -> EmailAccount:
        """Upsert the single email account."""
        existing = await self.get_account()
        encrypted_pwd = encrypt_password(data.password)
        caldav_url = data.caldav_url
        if data.calendar_provider == "google_api":
            from shogun.services.calendar_service import google_caldav_url

            credentials = data.calendar_credentials or {}
            caldav_url = google_caldav_url(
                data.email_address,
                credentials.get("calendar_id") if isinstance(credentials, dict) else None,
            )

        fields = {
            "provider": data.provider,
            "display_name": data.display_name,
            "email_address": data.email_address,
            "protocol": data.protocol,
            "imap_host": data.imap_host,
            "imap_port": data.imap_port,
            "imap_use_ssl": data.imap_use_ssl,
            "smtp_host": data.smtp_host,
            "smtp_port": data.smtp_port,
            "smtp_use_ssl": data.smtp_use_ssl,
            "username": data.username,
            "encrypted_password": encrypted_pwd,
            "caldav_url": caldav_url,
            "calendar_provider": data.calendar_provider,
            "calendar_credentials": data.calendar_credentials,
            "is_active": True,
        }

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            await self.session.flush()
            await self.session.commit()
            return existing
        else:
            new_acc = await self.create(**fields)
            await self.session.commit()
            return new_acc

    async def remove_account(self) -> bool:
        """Delete the single email account."""
        acc = await self.get_account()
        if not acc:
            return False
        await self.session.delete(acc)
        await self.session.commit()
        return True

    async def test_connection(self, data: EmailAccountCreate | EmailAccountUpdate) -> dict[str, Any]:
        """Test connection to IMAP/SMTP without modifying DB."""
        password = data.password
        if not password and isinstance(data, EmailAccountUpdate):
            acc = await self.get_account()
            if acc:
                password = decrypt_password(acc.encrypted_password)

        if not password:
            return {
                "ok": False,
                "imap_ok": False,
                "smtp_ok": False,
                "message": "Password is required to test connection.",
            }

        imap_ok = False
        smtp_ok = False
        err_msg = []

        # Test IMAP
        def test_imap():
            try:
                if data.imap_use_ssl:
                    client = imaplib.IMAP4_SSL(data.imap_host, data.imap_port)
                else:
                    client = imaplib.IMAP4(data.imap_host, data.imap_port)
                client.login(data.username, password)
                client.logout()
                return True, None
            except Exception as e:
                return False, f"IMAP Error: {str(e)}"

        # Test SMTP
        def test_smtp():
            try:
                if data.smtp_use_ssl:
                    server = smtplib.SMTP_SSL(data.smtp_host, data.smtp_port, timeout=10)
                else:
                    server = smtplib.SMTP(data.smtp_host, data.smtp_port, timeout=10)
                    server.ehlo()
                    try:
                        server.starttls()
                        server.ehlo()
                    except Exception:
                        pass
                server.login(data.username, password)
                server.quit()
                return True, None
            except Exception as e:
                return False, f"SMTP Error: {str(e)}"

        try:
            imap_ok, imap_err = await asyncio.to_thread(test_imap)
            if imap_err:
                err_msg.append(imap_err)
        except Exception as e:
            err_msg.append(f"IMAP test thread exception: {str(e)}")

        try:
            smtp_ok, smtp_err = await asyncio.to_thread(test_smtp)
            if smtp_err:
                err_msg.append(smtp_err)
        except Exception as e:
            err_msg.append(f"SMTP test thread exception: {str(e)}")

        ok = imap_ok and smtp_ok
        return {
            "ok": ok,
            "imap_ok": imap_ok,
            "smtp_ok": smtp_ok,
            "message": "Connection details are valid." if ok else " / ".join(err_msg),
        }

    # ── Mail Actions with Permission Enforcement ───────────────────────

    async def fetch_folders(self) -> list[str]:
        """Fetch IMAP folders."""
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email account configured")
        await require_comms_permission("perm_read_mail")

        password = decrypt_password(acc.encrypted_password)

        def _get_folders():
            if acc.imap_use_ssl:
                mail = imaplib.IMAP4_SSL(acc.imap_host, acc.imap_port)
            else:
                mail = imaplib.IMAP4(acc.imap_host, acc.imap_port)
            mail.login(acc.username, password)
            status, folder_list = mail.list()
            mail.logout()

            if status != "OK":
                return ["INBOX"]

            folders = []
            for f in folder_list:
                name = _parse_imap_list_line(f)
                if name:
                    folders.append(name)

            deduped = list(dict.fromkeys(folders))
            return sorted(deduped, key=lambda x: (x.upper() != "INBOX", x.lower()))

        try:
            return await asyncio.to_thread(_get_folders)
        except Exception:
            # Fallback to defaults if IMAP list fails
            return ["INBOX", "Sent", "Drafts", "Trash", "Archive"]

    async def fetch_messages(self, folder: str = "INBOX", page: int = 1, per_page: int = 20) -> dict[str, Any]:
        """Fetch list of messages from a folder (paginated)."""
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email account configured")
        await require_comms_permission("perm_read_mail")

        password = decrypt_password(acc.encrypted_password)

        def _get_msgs():
            if acc.imap_use_ssl:
                mail = imaplib.IMAP4_SSL(acc.imap_host, acc.imap_port)
            else:
                mail = imaplib.IMAP4(acc.imap_host, acc.imap_port)
            mail.login(acc.username, password)

            # Select folder
            status, _ = _select_mailbox(mail, folder)
            if status != "OK":
                mail.logout()
                return [], 0
            status, messages = mail.uid("search", None, "ALL")
            if status != "OK" or not messages[0]:
                mail.logout()
                return [], 0

            uids = messages[0].split()
            total = len(uids)
            uids.reverse()  # Newest first

            # Paginate
            start = (page - 1) * per_page
            end = start + per_page
            page_uids = uids[start:end]

            if not page_uids:
                mail.logout()
                return [], total

            uid_seq = b",".join(page_uids).decode()
            # Fetch headers + flags + mime structure + body preview snippet (first 500 bytes)
            status, fetch_data = mail.uid(
                "fetch",
                uid_seq,
                "(RFC822.HEADER FLAGS BODY.PEEK[1.MIME] BODY.PEEK[1]<0.500>)",
            )
            if status != "OK":
                mail.logout()
                return [], total

            messages_dict = {}
            current_uid = None

            for item in fetch_data:
                if isinstance(item, tuple):
                    meta_str = item[0].decode("utf-8", errors="ignore")
                    uid_match = re.search(r"UID\s+(\d+)", meta_str, re.IGNORECASE)
                    if uid_match:
                        current_uid = uid_match.group(1)
                        if current_uid not in messages_dict:
                            messages_dict[current_uid] = {
                                "uid": current_uid,
                                "header_bytes": b"",
                                "mime_bytes": b"",
                                "body_bytes": b"",
                                "flags_str": ""
                            }

                    if current_uid:
                        flags_match = re.search(r"FLAGS\s+\((.*?)\)", meta_str, re.IGNORECASE)
                        if flags_match:
                            messages_dict[current_uid]["flags_str"] = flags_match.group(1)

                        if "RFC822.HEADER" in meta_str:
                            messages_dict[current_uid]["header_bytes"] = item[1]
                        elif "BODY[1.MIME]" in meta_str or "BODY.PEEK[1.MIME]" in meta_str:
                            messages_dict[current_uid]["mime_bytes"] = item[1]
                        elif "BODY[1]" in meta_str or "BODY.PEEK[1]" in meta_str:
                            messages_dict[current_uid]["body_bytes"] = item[1]
                elif isinstance(item, bytes):
                    item_str = item.decode("utf-8", errors="ignore")
                    uid_match = re.search(r"UID\s+(\d+)", item_str, re.IGNORECASE)
                    if uid_match:
                        current_uid = uid_match.group(1)
                        if current_uid not in messages_dict:
                            messages_dict[current_uid] = {
                                "uid": current_uid,
                                "header_bytes": b"",
                                "mime_bytes": b"",
                                "body_bytes": b"",
                                "flags_str": ""
                            }
                    flags_match = re.search(r"FLAGS\s+\((.*?)\)", item_str, re.IGNORECASE)
                    if current_uid and flags_match:
                        messages_dict[current_uid]["flags_str"] = flags_match.group(1)

            parsed_messages = []
            for uid_bytes in page_uids:
                uid_str = uid_bytes.decode()
                if uid_str in messages_dict:
                    msg_data = messages_dict[uid_str]

                    # Parse standard headers
                    msg = email.message_from_bytes(msg_data["header_bytes"])
                    subject = parse_header_str(msg.get("Subject", "(No Subject)"))
                    from_addr = parse_header_str(msg.get("From", "(Unknown Sender)"))
                    to_addr = parse_header_str(msg.get("To", "(Unknown Recipient)"))
                    date_str = parse_header_str(msg.get("Date", ""))
                    is_read = "\\Seen" in msg_data["flags_str"]

                    # Generate and decode body preview
                    preview = ""
                    if msg_data["body_bytes"]:
                        # Use the MIME headers of part 1 if available, otherwise fallback to the main headers
                        mime_headers = msg_data["mime_bytes"] if msg_data["mime_bytes"] else msg_data["header_bytes"]
                        virtual_part_bytes = mime_headers + b"\r\n\r\n" + msg_data["body_bytes"]
                        try:
                            part = email.message_from_bytes(virtual_part_bytes)
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset() or "utf-8"
                                text = payload.decode(charset, errors="replace")
                            else:
                                text = ""
                        except Exception:
                            # Direct decode fallback
                            try:
                                text = msg_data["body_bytes"].decode("utf-8", errors="replace")
                            except Exception:
                                text = ""

                        # Strip HTML tags
                        text = re.sub(r"<[^>]*>", " ", text)
                        # Normalize whitespace
                        text = re.sub(r"\s+", " ", text).strip()
                        preview = text[:150]

                    # Detect attachments from headers
                    content_type = msg.get("Content-Type", "")
                    has_attachments = "multipart/mixed" in content_type.lower()

                    parsed_messages.append({
                        "uid": uid_str,
                        "from_address": from_addr,
                        "to_address": to_addr,
                        "subject": subject,
                        "date": date_str,
                        "body_preview": preview,
                        "is_read": is_read,
                        "has_attachments": has_attachments,
                    })

            mail.logout()
            return parsed_messages, total

        parsed_list, total_count = await asyncio.to_thread(_get_msgs)
        return {"messages": parsed_list, "total": total_count}

    async def fetch_message(self, uid: str, folder: str = "INBOX") -> dict[str, Any]:
        """Fetch full details of a single message."""
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email account configured")
        await require_comms_permission("perm_read_mail")

        password = decrypt_password(acc.encrypted_password)

        def _get_msg():
            if acc.imap_use_ssl:
                mail = imaplib.IMAP4_SSL(acc.imap_host, acc.imap_port)
            else:
                mail = imaplib.IMAP4(acc.imap_host, acc.imap_port)
            mail.login(acc.username, password)
            status, _ = _select_mailbox(mail, folder)
            if status != "OK":
                mail.logout()
                raise ValueError(f"Could not select mail folder: {folder}")

            status, fetch_data = mail.uid("fetch", uid, "(RFC822 FLAGS)")
            if status != "OK" or not fetch_data:
                mail.logout()
                raise HTTPException(status_code=404, detail="Message not found")

            raw_email = None
            flags_str = ""
            for item in fetch_data:
                if isinstance(item, tuple):
                    raw_email = item[1]
                    meta = item[0].decode("utf-8", errors="ignore")
                    flags_match = re.search(r"FLAGS\s+\((.*?)\)", meta, re.IGNORECASE)
                    if flags_match:
                        flags_str = flags_match.group(1)

            if not raw_email:
                mail.logout()
                raise HTTPException(status_code=404, detail="Message data empty")

            msg = email.message_from_bytes(raw_email)
            is_read = "\\Seen" in flags_str

            subject = parse_header_str(msg.get("Subject", "(No Subject)"))
            from_addr = parse_header_str(msg.get("From", "(Unknown Sender)"))
            to_addr = parse_header_str(msg.get("To", "(Unknown Recipient)"))
            date_str = parse_header_str(msg.get("Date", ""))

            body_text = ""
            body_html = ""
            attachments = []

            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disp = str(part.get("Content-Disposition"))

                    if content_type == "text/plain" and "attachment" not in content_disp:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_text += payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    elif content_type == "text/html" and "attachment" not in content_disp:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_html += payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    elif "attachment" in content_disp or part.get_filename():
                        filename = parse_header_str(part.get_filename())
                        if filename:
                            attachments.append({
                                "filename": filename,
                                "content_type": content_type,
                                "size": len(part.get_payload(decode=True) or b""),
                            })
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body_text = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
                if msg.get_content_type() == "text/html":
                    body_html = body_text

            # Mark as read implicitly
            if not is_read:
                mail.uid("store", uid, "+FLAGS", "\\Seen")

            mail.logout()

            # Simple text preview
            preview = body_text[:150].strip() if body_text else (body_html[:150].strip() if body_html else "")
            # Remove html tags for preview if it was html
            preview = re.sub(r"<[^>]*>", "", preview)[:150]

            return {
                "uid": uid,
                "from_address": from_addr,
                "to_address": to_addr,
                "subject": subject,
                "date": date_str,
                "body_preview": preview,
                "is_read": True,
                "has_attachments": len(attachments) > 0,
                "body_html": body_html or f"<pre>{body_text}</pre>",
                "body_text": body_text,
                "attachments": attachments,
            }

        return await asyncio.to_thread(_get_msg)

    async def send_email(self, req: EmailComposeRequest) -> dict[str, Any]:
        """Send email via SMTP."""
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email account configured")
        await require_comms_permission("perm_send_mail")

        password = decrypt_password(acc.encrypted_password)

        def _send():
            msg = MIMEMultipart("alternative")
            msg["Subject"] = req.subject
            msg["From"] = acc.email_address
            msg["To"] = req.to_address
            if req.cc_address:
                msg["Cc"] = req.cc_address
            if req.bcc_address:
                msg["Bcc"] = req.bcc_address

            # Plain text and HTML version of message body
            part1 = MIMEText(req.body, "plain")
            part2 = MIMEText(f"<html><body>{req.body.replace(chr(10), '<br>')}</body></html>", "html")
            msg.attach(part1)
            msg.attach(part2)

            recipients = [req.to_address]
            if req.cc_address:
                recipients.extend([c.strip() for c in req.cc_address.split(",")])
            if req.bcc_address:
                recipients.extend([b.strip() for b in req.bcc_address.split(",")])

            if acc.smtp_use_ssl:
                server = smtplib.SMTP_SSL(acc.smtp_host, acc.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(acc.smtp_host, acc.smtp_port, timeout=15)
                server.ehlo()
                try:
                    server.starttls()
                    server.ehlo()
                except Exception:
                    pass

            server.login(acc.username, password)
            server.sendmail(acc.email_address, recipients, msg.as_string())
            server.quit()
            return {"ok": True, "message": "Email sent successfully."}

        return await asyncio.to_thread(_send)

    async def mark_read(self, uid: str, folder: str = "INBOX", read: bool = True) -> dict[str, Any]:
        """Mark email as read/unread."""
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email account configured")
        await require_comms_permission("perm_read_mail")

        password = decrypt_password(acc.encrypted_password)

        def _store():
            if acc.imap_use_ssl:
                mail = imaplib.IMAP4_SSL(acc.imap_host, acc.imap_port)
            else:
                mail = imaplib.IMAP4(acc.imap_host, acc.imap_port)
            mail.login(acc.username, password)
            status, _ = _select_mailbox(mail, folder)
            if status != "OK":
                mail.logout()
                raise ValueError(f"Could not select mail folder: {folder}")

            op = "+FLAGS" if read else "-FLAGS"
            mail.uid("store", uid, op, "\\Seen")
            mail.logout()
            return {"ok": True, "message": f"Message marked as {'read' if read else 'unread'}."}

        return await asyncio.to_thread(_store)

    async def delete_message(self, uid: str, folder: str = "INBOX") -> dict[str, Any]:
        """Move message to Trash folder or delete it."""
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email account configured")
        await require_comms_permission("perm_delete_mail")

        password = decrypt_password(acc.encrypted_password)

        def _delete():
            if acc.imap_use_ssl:
                mail = imaplib.IMAP4_SSL(acc.imap_host, acc.imap_port)
            else:
                mail = imaplib.IMAP4(acc.imap_host, acc.imap_port)
            mail.login(acc.username, password)
            status, _ = _select_mailbox(mail, folder)
            if status != "OK":
                mail.logout()
                raise ValueError(f"Could not select mail folder: {folder}")

            # Move to Trash if possible, else mark deleted and expunge
            status, folder_list = mail.list()
            trash_folder = None
            if status == "OK":
                for f in folder_list:
                    name = _parse_imap_list_line(f)
                    if not name:
                        continue
                    f_str = name.lower()
                    if "trash" in f_str or "bin" in f_str:
                        trash_folder = name
                        break

            if trash_folder and trash_folder.lower() != folder.lower():
                try:
                    result = mail.uid("copy", uid, _quote_mailbox(trash_folder))
                    if result[0] == "OK":
                        mail.uid("store", uid, "+FLAGS", "\\Deleted")
                        mail.expunge()
                        mail.logout()
                        return {"ok": True, "message": f"Message moved to {trash_folder}."}
                except Exception:
                    pass

            # Fallback to direct delete
            mail.uid("store", uid, "+FLAGS", "\\Deleted")
            mail.expunge()
            mail.logout()
            return {"ok": True, "message": "Message deleted permanently."}

        return await asyncio.to_thread(_delete)
