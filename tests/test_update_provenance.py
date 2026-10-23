from __future__ import annotations

import pytest

from shogun.api import updates


class _Response:
    def __init__(self, status_code: int, *, payload: dict | None = None, content: bytes = b""):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content

    def json(self) -> dict:
        return self._payload


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["", "private-token"])
async def test_archive_download_is_pinned_to_resolved_sha_even_if_main_advances(token):
    resolved_sha = "a" * 40

    class Client:
        def __init__(self):
            self.urls: list[str] = []

        async def get(self, url: str, **_kwargs):
            self.urls.append(url)
            if url.endswith("/commits/main"):
                return _Response(200, payload={"sha": resolved_sha})
            if resolved_sha in url:
                return _Response(200, content=b"archive-for-resolved-sha")
            # This represents main advancing between lookup and download. The
            # updater must never request this mutable archive after resolution.
            return _Response(200, content=b"archive-for-newer-main")

    client = Client()
    response, source_commit, warnings, archive_url = await updates._download_update_archive(
        client,
        repo="AlphaHorizon-AI/Shogun",
        branch="main",
        token=token,
        headers={"User-Agent": "test"},
    )

    assert source_commit == resolved_sha
    assert warnings == []
    assert resolved_sha in archive_url
    assert response.content == b"archive-for-resolved-sha"
    assert len(client.urls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [None, _Response(403), _Response(200, payload={"sha": "invalid"})])
async def test_commit_lookup_failure_stops_without_downloading_a_branch(response):
    from fastapi import HTTPException

    class Client:
        def __init__(self):
            self.urls: list[str] = []

        async def get(self, url: str, **_kwargs):
            self.urls.append(url)
            if response is None:
                raise RuntimeError("lookup unavailable")
            return response

    client = Client()
    with pytest.raises(HTTPException) as error:
        await updates._download_update_archive(
            client,
            repo="AlphaHorizon-AI/Shogun",
            branch="main",
            token="",
            headers={},
        )
    assert error.value.status_code == 502
    assert len(client.urls) == 1
    assert client.urls[0].endswith("/commits/main")


def test_missing_provenance_never_turns_applied_update_into_failure(tmp_path, monkeypatch):
    def fail_to_write(*_args, **_kwargs):
        raise OSError("read-only evidence directory")

    monkeypatch.setattr(updates, "write_release_metadata_evidence", fail_to_write)
    warnings: list[str] = []

    updates._persist_update_release_evidence(
        tmp_path,
        {"version": "2.0.0", "build": 200},
        None,
        warnings,
    )

    assert warnings == ["The update was applied, but local release provenance could not be recorded."]
