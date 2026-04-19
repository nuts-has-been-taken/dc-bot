from unittest.mock import AsyncMock, patch

import pytest

from src.agent.tools.job_analysis_mcp import (
    analyze_104_job_impl,
    extract_url_from_query,
    validate_url_security,
)


def test_extract_url_from_query_finds_link():
    q = "請分析 https://www.104.com.tw/job/abc 這個職缺"
    assert extract_url_from_query(q) == "https://www.104.com.tw/job/abc"


def test_extract_url_from_query_returns_none_when_no_url():
    assert extract_url_from_query("台積電 IT") is None


def test_validate_url_security_rejects_internal():
    assert not validate_url_security("http://localhost/x")
    assert not validate_url_security("http://192.168.0.1/x")
    assert not validate_url_security("ftp://example.com/x")


def test_validate_url_security_allows_public_https():
    assert validate_url_security("https://www.104.com.tw/job/abc")


@pytest.mark.asyncio
async def test_analyze_with_url_calls_fetcher():
    with patch(
        "src.agent.tools.job_analysis_mcp.fetch_webpage_content",
        new=AsyncMock(return_value="【職位名稱】後端工程師\n"),
    ) as mock_fetch:
        result = await analyze_104_job_impl(
            "https://www.104.com.tw/job/abc"
        )
    mock_fetch.assert_called_once()
    assert "後端工程師" in result["webpage_content"]


@pytest.mark.asyncio
async def test_analyze_without_url_returns_no_webpage_content():
    result = await analyze_104_job_impl("台積電 IT 評價")
    assert result["webpage_content"] is None
    assert result["query"] == "台積電 IT 評價"
