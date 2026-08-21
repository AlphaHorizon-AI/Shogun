"""Create a local Primary Admin setup link without putting its token in HTTP.

The control-plane credential is carried in the URL fragment. Browsers do not send
fragments in HTTP requests, and the Tenshu removes the fragment synchronously
before React starts or any API request is made.
"""

from __future__ import annotations

import argparse
import os
from urllib.parse import quote, urlsplit, urlunsplit


def build_server_setup_url(token: str, origin: str = "http://127.0.0.1:8000") -> str:
    """Return a setup URL whose credential is confined to the fragment."""

    normalized_token = token.strip()
    if (
        len(normalized_token) < 32
        or normalized_token.casefold().startswith("change-me")
        or any(not 0x21 <= ord(character) <= 0x7E for character in normalized_token)
    ):
        raise ValueError("A configured infrastructure administrator token is required.")

    parsed = urlsplit(origin.strip())
    try:
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        hostname = None
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(
            "The setup origin must be an HTTP(S) origin without credentials, a path, "
            "a query, or a fragment."
        )

    canonical_origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")
    encoded_token = quote(normalized_token, safe="")
    return f"{canonical_origin}/setup#infrastructure_token={encoded_token}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Print a private Primary Admin bootstrap link to the current terminal. "
            "Treat its fragment as a credential."
        )
    )
    parser.add_argument(
        "--origin",
        default="http://127.0.0.1:8000",
        help="Browser-visible Shogun origin (default: http://127.0.0.1:8000)",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    token = os.environ.get("SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN", "")
    try:
        setup_url = build_server_setup_url(token, args.origin)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(setup_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
