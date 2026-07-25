"""Installer-only command for recording an explicit telemetry choice."""

from __future__ import annotations

import argparse
import asyncio

from shogun.telemetry.service import telemetry_service


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("enable", "disable"))
    parser.add_argument("--notice-version", default="")
    args = parser.parse_args()
    if args.action == "enable":
        asyncio.run(telemetry_service.enable(
            args.notice_version,
            actor="installer",
            register_immediately=False,
        ))
    else:
        asyncio.run(telemetry_service.disable())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
