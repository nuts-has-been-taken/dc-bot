from unittest.mock import patch

import pytest

from src.agent.tools.job_search_mcp import (
    JobSearchParams,
    convert_params,
    search_104_jobs_impl,
)


def test_convert_params_translates_chinese_labels():
    params = JobSearchParams(
        keyword="Python",
        area=["台北市"],
        job_category=["軟體／工程類人員"],
        education="大學",
        salary_range="50000-",
    )
    converted = convert_params(params)
    assert converted["keyword"] == "Python"
    assert converted["area"] == ["6001001000"]
    assert converted["salary_min"] == 50000
    assert "salary_max" not in converted


def test_convert_params_drops_unknown_area():
    params = JobSearchParams(keyword="Python", area=["火星"])
    converted = convert_params(params)
    assert "area" not in converted


@pytest.mark.asyncio
async def test_search_impl_calls_core_and_formats():
    fake_jobs = [
        {
            "jobName": "Python Engineer",
            "custName": "ACME",
            "jobAddrNoDesc": "台北市",
            "salaryLow": 50000,
            "salaryHigh": 80000,
            "optionEdu": ["4"],
            "period": 3,
            "appearDate": "2026-04-01",
            "link": {"job": "https://x"},
            "description": "A job.",
        }
    ]
    with patch(
        "src.agent.tools.job_search_mcp.search_104_jobs",
        return_value=fake_jobs,
    ) as mock_core:
        result = await search_104_jobs_impl(
            keyword="Python", area=["台北市"]
        )
    mock_core.assert_called_once()
    assert result["total"] == 1
    assert "Python Engineer" in result["formatted"]
