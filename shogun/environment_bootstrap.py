"""Create and protect the local desktop environment file.

The infrastructure administrator token is deliberately persisted only in the
installation's ``.env`` file.  This module never returns or prints secret
values; the desktop launcher reads the token through normal settings loading
and transfers it to the browser in a URL fragment.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import secrets
import stat
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

_SECRET_KEYS = (
    "SECRET_KEY",
    "VAULT_ENCRYPTION_KEY",
    "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN",
    "A2A_ENCRYPTION_KEY",
)
_ASSIGNMENT = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?)"
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*?)$"
)


def _unquoted(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value


def _needs_secret(value: str) -> bool:
    normalized = _unquoted(value).casefold()
    return len(normalized) < 32 or normalized.startswith("change-me")


def build_desktop_browser_url(url: str, token: str) -> str:
    """Attach an encoded credential as a fragment, never as an HTTP query."""
    parsed = urlsplit(url)
    normalized_token = token.strip()
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("The desktop browser URL must be an HTTP(S) URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("The desktop browser URL must not contain user information.")
    hostname = parsed.hostname.rstrip(".").casefold()
    loopback = hostname == "localhost"
    if not loopback:
        try:
            loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            loopback = False
    if not loopback:
        raise ValueError("The desktop browser URL must use a loopback host.")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("The desktop browser URL contains an invalid port.") from exc
    if len(normalized_token) < 32 or normalized_token.casefold().startswith("change-me"):
        raise ValueError("A strong infrastructure administrator token is required.")
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.query,
            f"infrastructure_token={quote(normalized_token, safe='')}",
        )
    )


def _assignment_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines(keepends=True):
        match = _ASSIGNMENT.match(line)
        if match:
            values[match.group("key").upper()] = match.group("value")
    return values


def _secure_contents(text: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    generated = {key: secrets.token_urlsafe(48) for key in _SECRET_KEYS}
    seen: set[str] = set()
    deployment_mode = _unquoted(
        _assignment_values(text).get("DEPLOYMENT_MODE", "desktop")
    ).casefold()
    secured_lines: list[str] = []

    for line in text.splitlines(keepends=True):
        match = _ASSIGNMENT.match(line)
        if not match:
            secured_lines.append(line)
            continue

        key = match.group("key").upper()
        value = match.group("value")
        line_ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        if key in _SECRET_KEYS:
            seen.add(key)
            if _needs_secret(value):
                secured_lines.append(f"{key}={generated[key]}{line_ending}")
                continue
        elif (
            key == "API_HOST"
            and deployment_mode != "server"
            and _unquoted(value) == "0.0.0.0"
        ):
            secured_lines.append(f"API_HOST=127.0.0.1{line_ending}")
            continue
        secured_lines.append(line)

    secured = "".join(secured_lines)
    missing = [key for key in _SECRET_KEYS if key not in seen]
    if missing:
        if secured and not secured.endswith(("\n", "\r")):
            secured += newline
        secured += "".join(f"{key}={generated[key]}{newline}" for key in missing)
    return secured


def _default_contents(root: Path) -> str:
    return (
        "APP_ENV=production\n"
        "DEPLOYMENT_MODE=desktop\n"
        "DEBUG=false\n"
        "API_HOST=127.0.0.1\n"
        "API_PORT=8000\n"
        "DATABASE_URL=sqlite+aiosqlite:///./data/shogun.db\n"
        "QDRANT_PATH=./data/qdrant\n"
        "SECRET_KEY=\n"
        "VAULT_ENCRYPTION_KEY=\n"
        "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN=\n"
        "A2A_ENCRYPTION_KEY=\n"
        f"VAULT_PATH={root / 'vault'}\n"
        f"LOG_PATH={root / 'logs'}\n"
        f"CONFIG_PATH={root / 'configs'}\n"
    )


def _write_private(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    temporary_path = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            descriptor = -1
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _restrict_windows_acl(path: Path) -> None:
    identity = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "[Security.Principal.WindowsIdentity]::GetCurrent().User.Value",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not identity.startswith("S-"):
        raise RuntimeError("Could not resolve the current Windows account SID")
    subprocess.run(
        [
            "icacls.exe",
            str(path),
            "/inheritance:r",
            "/grant:r",
            f"*{identity}:(F)",
            "*S-1-5-18:(F)",
            "*S-1-5-32-544:(F)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def restrict_environment_permissions(path: Path) -> None:
    """Restrict ``path`` to the installing account and trusted OS principals."""
    if os.name == "nt":
        _restrict_windows_acl(path)
        return
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def secure_environment_file(path: Path) -> bool:
    """Repair bootstrap placeholders and return whether content changed."""
    original = path.read_text(encoding="utf-8")
    secured = _secure_contents(original)
    changed = secured != original
    if changed:
        _write_private(path, secured)
    restrict_environment_permissions(path)
    return changed


def ensure_desktop_environment(
    root: Path,
    *,
    example_path: Path | None = None,
) -> tuple[Path, bool]:
    """Create/repair a private desktop ``.env`` without exposing its secrets."""
    root = root.resolve()
    env_path = root / ".env"
    created = not env_path.exists()
    if created:
        source = example_path or root / ".env.example"
        contents = (
            source.read_text(encoding="utf-8")
            if source.is_file()
            else _default_contents(root)
        )
        _write_private(env_path, _secure_contents(contents))
        restrict_environment_permissions(env_path)
    else:
        secure_environment_file(env_path)
    return env_path, created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare Shogun's desktop environment")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    ensure_desktop_environment(args.root)
    # Deliberately generic: credentials must never reach terminal captures or logs.
    print("Shogun desktop environment is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
