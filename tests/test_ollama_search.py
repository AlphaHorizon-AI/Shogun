import pytest

from shogun.api.system import _parse_ollama_search_html, scan_local_models


def test_current_ollama_search_markup_is_parsed():
    html = """
    <ul>
      <li class="flex items-baseline border-b border-neutral-200 py-6">
        <a href="/library/qwen3.5" class="group w-full">
          <h2><span>qwen3.5</span></h2>
          <p class="max-w-lg break-words text-neutral-800">A capable &amp; efficient model.</p>
          <span>vision</span><span>tools</span><span>0.8b</span><span>9b</span>
          <span>16.5M</span><span> Pulls</span>
          <span>64</span><span> Tags</span>
          <span>Updated&nbsp;</span><span>2 months ago</span>
        </a>
      </li>
      <li hx-get="/search?page=2" hx-trigger="revealed"></li>
    </ul>
    """

    models, has_more = _parse_ollama_search_html(html, 1)

    assert has_more is True
    assert models == [{
        "id": "qwen3.5",
        "name": "qwen3.5",
        "description": "A capable & efficient model.",
        "sizes": ["0.8b", "9b"],
        "capabilities": ["vision", "tools"],
        "pulls": "16.5M",
        "tag_count": 64,
        "updated": "2 months ago",
    }]


def test_legacy_ollama_search_markup_remains_supported():
    html = """
    <li x-test-model>
      <span x-test-search-response-title>gemma3</span>
      <p class="break-words">Vision model</p>
      <span x-test-size>4b</span><span x-test-capability>vision</span>
      <span x-test-pull-count>10M</span><span x-test-tag-count>12</span>
      <span x-test-updated>1 week ago</span>
    </li>
    """

    models, has_more = _parse_ollama_search_html(html, 1)

    assert has_more is False
    assert models[0]["id"] == "gemma3"
    assert models[0]["capabilities"] == ["vision"]


@pytest.mark.asyncio
async def test_scan_accepts_ollama_home_or_models_directory(tmp_path):
    manifest = tmp_path / "models" / "manifests" / "registry.ollama.ai" / "library" / "qwen3" / "8b"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")

    result = await scan_local_models(str(tmp_path))

    assert result.success is True
    assert result.data == ["qwen3:8b"]
