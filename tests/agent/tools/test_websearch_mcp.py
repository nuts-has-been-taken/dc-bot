from pathlib import Path
from unittest.mock import patch

import pytest

from src.agent.tools import websearch_mcp as m
from src.agent.tools.websearch_mcp import (
    _format_web_results,
    normalize_image_results,
    normalize_web_results,
    try_consume_quota,
    web_search_impl,
)

def _allow_quota():
    """Context manager used INSIDE async tests so the with-block lives within
    the awaited coroutine. (Using patch as a decorator over an async function
    exits before the coroutine runs — see comments at call sites.)"""
    return patch(
        "src.agent.tools.websearch_mcp.try_consume_quota",
        return_value=(True, 0, 1000),
    )


# ───────────────────────── normalization ─────────────────────────


def test_normalize_web_results_maps_fields():
    data = {
        "web": {
            "results": [
                {
                    "title": "台積電",
                    "url": "https://tsmc.com",
                    "description": "晶圓代工",
                    "extra_snippets": ["更多資訊"],
                }
            ]
        }
    }
    results = normalize_web_results(data)
    assert results[0]["title"] == "台積電"
    assert results[0]["url"] == "https://tsmc.com"
    assert results[0]["snippet"] == "晶圓代工"
    assert results[0]["extra_snippets"] == ["更多資訊"]


def test_normalize_image_results_maps_urls():
    data = {
        "results": [
            {
                "title": "pic",
                "description": "desc",
                "thumbnail": {"src": "https://thumb.jpg"},
                "properties": {
                    "url": "https://cdn/full.jpg",
                    "width": 1920,
                    "height": 1080,
                },
                "meta_url": {
                    "netloc": "www.src.com",
                    "favicon": "https://icon",
                },
            }
        ]
    }
    results = normalize_image_results(data)
    item = results[0]
    assert item["image_url"] == "https://cdn/full.jpg"
    assert item["thumbnail_url"] == "https://thumb.jpg"
    assert item["source_url"] == "www.src.com"
    assert item["source_favicon"] == "https://icon"
    assert item["width"] == 1920
    assert item["height"] == 1080


def test_format_web_results_omits_empty_snippet():
    text = _format_web_results([{"title": "A", "url": "https://a", "snippet": ""}])
    assert "摘要" not in text


# ───────────────────────── impl ─────────────────────────


@pytest.mark.asyncio
async def test_web_search_success_web():
    payload = {"web": {"results": [{"title": "台積電", "url": "https://tsmc.com", "description": "晶圓代工"}]}}
    with _allow_quota(), patch(
        "src.agent.tools.websearch_mcp.requests.get",
        return_value=_ok(payload),
    ) as mock_get:
        result = await web_search_impl(query="台積電", search_type="web", api_key="test-key")

    assert result["search_type"] == "web"
    assert mock_get.call_args.args[0] == "https://api.search.brave.com/res/v1/web/search"
    assert mock_get.call_args.kwargs["headers"]["X-Subscription-Token"] == "test-key"
    assert "台積電" in result["formatted"]


@pytest.mark.asyncio
async def test_image_search_success():
    payload = {
        "results": [
            {
                "title": "cat",
                "thumbnail": {"src": "https://thumb.jpg"},
                "properties": {"url": "https://img.jpg", "width": 640, "height": 480},
                "meta_url": {"netloc": "www.cats.org"},
            }
        ]
    }
    with _allow_quota(), patch(
        "src.agent.tools.websearch_mcp.requests.get",
        return_value=_ok(payload),
    ) as mock_get:
        result = await web_search_impl(query="cat", search_type="image", api_key="test-key")

    assert result["search_type"] == "image"
    assert mock_get.call_args.args[0] == "https://api.search.brave.com/res/v1/images/search"
    assert result["results"][0]["image_url"] == "https://img.jpg"
    assert "圖片" in result["formatted"]


@pytest.mark.asyncio
async def test_context_search_success():
    payload = {
        "grounding": {
            "generic": [
                {
                    "url": "https://a.com",
                    "title": "A 站",
                    "snippets": ["NVIDIA Blackwell 已量產", "第二段內容"],
                },
            ]
        },
        "sources": {
            "https://a.com": {"title": "A 站", "hostname": "a.com"},
        },
    }
    with _allow_quota(), patch(
        "src.agent.tools.websearch_mcp.requests.get",
        return_value=_ok(payload),
    ) as mock_get:
        result = await web_search_impl(query="Blackwell", search_type="context", api_key="test-key")

    assert result["search_type"] == "context"
    assert mock_get.call_args.args[0] == "https://api.search.brave.com/res/v1/llm/context"
    src = result["results"][0]
    assert src["url"] == "https://a.com"
    assert src["title"] == "A 站"
    assert "NVIDIA Blackwell" in src["content"]
    assert "A 站" in result["formatted"]


@pytest.mark.asyncio
async def test_context_empty_grounding_returns_empty_results():
    payload = {"grounding": {"generic": []}, "sources": {}}
    with _allow_quota(), patch(
        "src.agent.tools.websearch_mcp.requests.get",
        return_value=_ok(payload),
    ):
        result = await web_search_impl(query="nothing", search_type="context", api_key="test-key")
    assert result["results"] == []
    assert "沒有找到" in result["formatted"]


@pytest.mark.asyncio
async def test_missing_key_returns_error():
    with _allow_quota(), patch("src.config.Config.BRAVE_SEARCH_API_KEY", None):
        result = await web_search_impl(query="hello")
    assert "error" in result
    assert "BRAVE_SEARCH_API_KEY" in result["error"]
    assert result["results"] == []


@pytest.mark.asyncio
async def test_http_error_429_returns_rate_limit_message():
    with _allow_quota(), patch(
        "src.agent.tools.websearch_mcp.requests.get",
        return_value=_failure(429),
    ):
        result = await web_search_impl(query="hello", api_key="test-key")
    assert "429" in result["error"]
    assert "額度" in result["error"]


# ───────────────────────── quota counter ─────────────────────────


def test_quota_counts_up_and_blocks_when_exhausted(tmp_path):
    fake_path = tmp_path / "brave_quota.json"
    with patch("src.agent.tools.websearch_mcp._quota_path", return_value=fake_path):
        # fill to 2 with limit 2
        assert try_consume_quota(2) == (True, 1, 2)
        assert try_consume_quota(2) == (True, 2, 2)
        # third call refused, does not increment
        assert try_consume_quota(2) == (False, 2, 2)
        assert fake_path.read_text().find('"count": 2') != -1


def test_quota_unlimited_when_limit_none(tmp_path):
    fake_path = tmp_path / "brave_quota.json"
    with patch("src.agent.tools.websearch_mcp._quota_path", return_value=fake_path):
        allowed, used, limit = try_consume_quota(None)
    assert allowed is True
    assert limit == -1


@pytest.mark.asyncio
async def test_impl_blocks_when_quota_exceeded(tmp_path):
    fake_path = tmp_path / "brave_quota.json"
    # used equals the limit -> quota is exhausted -> impl must refuse
    fake_path.write_text('{"count": 1000}')
    with patch(
        "src.agent.tools.websearch_mcp._quota_path", return_value=fake_path
    ), patch("src.config.Config.BRAVE_MONTHLY_LIMIT", 1000):
        result = await web_search_impl(query="anything", api_key="test-key")
    assert "error" in result
    assert "額度" in result["error"] or "1000" in result["error"]


# ───────────────────────── helpers ─────────────────────────


def _ok(data):
    class R:
        status_code = 200

        def json(self):
            return data

        def raise_for_status(self):
            return None

    return R()


def _failure(status):
    import requests

    class R:
        status_code = status

        def json(self):
            return {}

        def raise_for_status(self):
            raise requests.HTTPError(response=self)

    return R()
