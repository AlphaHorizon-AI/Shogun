"""Opt-in native smoke tests for a disposable macOS installation (see CI)."""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or os.environ.get("SHOGUN_MACOS_SMOKE") != "1",
    reason="requires an explicitly opted-in, disposable native macOS installation",
)


def test_installed_source_matches_expected_edition():
    expected = os.environ.get("SHOGUN_MACOS_EDITION", "yellow-label")
    if expected == "white-label":
        from shogun.productisation.distribution import EDITION

        assert EDITION == "white_label"
    else:
        from shogun.edition import EDITION_NAME

        assert expected == EDITION_NAME == "yellow-label"


def test_real_embedding_and_embedded_memory_roundtrip(tmp_path, monkeypatch):
    from shogun.config import settings
    from shogun.engine.vector_store import VectorStore

    monkeypatch.setattr(settings, "qdrant_url", None)
    monkeypatch.setattr(settings, "qdrant_path", tmp_path / "qdrant")
    store = VectorStore()
    memory_id = str(uuid.uuid4())
    try:
        store.ensure_collection()
        store.upsert(memory_id, "Shogun runs on an Apple Silicon Mac.")
        results = store.search("Shogun on a Mac", limit=1)
        assert results[0]["memory_id"] == memory_id
        store.close()
        assert store.collection_info()["points_count"] == 1
    finally:
        store.close()


def _wait_ready(client, process, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert process.poll() is None, "The desktop launcher exited before readiness"
        try:
            response = client.get("/api/v1/health")
            if response.status_code == 200 and response.json().get("status") == "ok":
                return
        except httpx.TransportError:
            pass
        time.sleep(0.5)
    pytest.fail("Shogun did not become ready within the startup timeout")


async def _browser_action(operation, description, timeout=30):
    print(description, flush=True)
    try:
        return await asyncio.wait_for(operation, timeout=timeout)
    except asyncio.TimeoutError:
        raise AssertionError(f"{description} timed out after {timeout} seconds") from None


@pytest.mark.asyncio
async def test_installed_launcher_setup_browsers_and_restart(tmp_path):
    from dotenv import dotenv_values
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright

    from shogun.environment_bootstrap import build_desktop_browser_url

    token = dotenv_values(ROOT / ".env")["SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN"]
    assert token
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    environment = {
        **os.environ,
        "API_HOST": "127.0.0.1", "API_PORT": str(port),
        "SHOGUN_NO_BROWSER": "true", "SHOGUN_BROWSER_URL": origin,
        "SHOGUN_SKIP_ENV_FILE": "false",
    }
    with (tmp_path / "server.log").open("w", encoding="utf-8") as log:
        completed = False
        process = subprocess.Popen(
            ["/bin/bash", str(ROOT / "start.sh")], cwd=tmp_path, env=environment,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            with httpx.Client(base_url=origin, timeout=5, trust_env=False) as client:
                _wait_ready(client, process)
                assert client.get("/").status_code == 200
                assert client.get("/setup").status_code == 200
                headers = {"X-Shogun-Infrastructure-Token": token}
                status = client.get("/api/v1/setup/status", headers=headers)
                assert status.status_code == 200
                assert status.json()["data"]["setup_complete"] is False
                print("Native launcher and authenticated setup API are ready", flush=True)
                playwright = await _browser_action(async_playwright().start(), "Starting Playwright")
                try:
                    for browser_type in (playwright.chromium, playwright.webkit):
                        browser = await _browser_action(
                            browser_type.launch(headless=True), f"Launching {browser_type.name}",
                        )
                        try:
                            context = await _browser_action(
                                browser.new_context(), f"Creating {browser_type.name} context",
                            )
                            page = await _browser_action(context.new_page(), f"Opening {browser_type.name} page")
                            errors = []
                            page.on("pageerror", lambda _error: errors.append("JavaScript error"))
                            # Do not include the private bootstrap URL in assertion output.
                            try:
                                await _browser_action(
                                    page.goto(build_desktop_browser_url(f"{origin}/setup", token)),
                                    f"Navigating {browser_type.name} to setup",
                                )
                            except PlaywrightError:
                                raise AssertionError("Setup navigation failed; private bootstrap URL omitted") from None
                            # The telemetry invitation also has an h2 and can
                            # render before the lazy-loaded setup form.
                            await _browser_action(
                                page.locator("input").first.wait_for(timeout=30_000),
                                f"Waiting for {browser_type.name} setup form",
                            )
                            fragment_removed = "#" not in page.url
                            assert fragment_removed, "The setup bootstrap fragment was not removed"
                            assert errors == []
                            await _browser_action(context.close(), f"Closing {browser_type.name} context", timeout=10)
                        finally:
                            await _browser_action(browser.close(), f"Closing {browser_type.name} browser", timeout=10)
                        print(f"{browser_type.name} setup smoke test passed", flush=True)
                finally:
                    await _browser_action(playwright.stop(), "Stopping Playwright", timeout=10)
                print("Requesting a supervised application restart", flush=True)
                restart = client.post("/api/v1/updates/restart", headers=headers)
                if os.environ.get("SHOGUN_MACOS_EDITION") == "white-label":
                    # White Label correctly blocks normal operations until its
                    # product identity and installation setup are complete.
                    assert restart.status_code == 409
                    assert restart.json()["detail"]["code"] == "WL_SETUP_REQUIRED"
                    # Exercise the supervisor from the test-owned process tree;
                    # do not weaken the product's readiness or permission gate.
                    import psutil

                    children = psutil.Process(process.pid).children()
                    servers = [child for child in children if "shogun" in child.cmdline()]
                    assert len(servers) == 1
                    marker = ROOT / ".states/restart-requested"
                    marker.parent.mkdir(parents=True, exist_ok=True)
                    marker.write_text("macOS smoke test restart\n", encoding="utf-8")
                    servers[0].terminate()
                else:
                    assert restart.status_code == 202
                # The launcher announces restart only after the old server has exited.
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    if "Restart requested. Starting Shogun again" in (tmp_path / "server.log").read_text():
                        break
                    time.sleep(0.5)
                else:
                    pytest.fail("The desktop launcher did not supervise the requested restart")
                _wait_ready(client, process)
                completed = True
        finally:
            if not completed:
                from urllib.parse import quote

                log.flush()
                output = (tmp_path / "server.log").read_text(encoding="utf-8", errors="replace")
                for secret in (token, quote(token, safe="")):
                    output = output.replace(secret, "[REDACTED]")
                print("\n".join(output.splitlines()[-120:]))
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
