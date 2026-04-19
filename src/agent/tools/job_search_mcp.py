"""MCP tool: search Taiwan 104 job listings."""

from dataclasses import dataclass, field
from typing import Any

from src.core.job104 import search_104_jobs
from src.core.mappings import (
    AREA_MAP,
    EDUCATION_MAP,
    JOB_TYPE_MAP,
    SORT_BY_MAP,
)


@dataclass
class JobSearchParams:
    keyword: str
    area: list[str] = field(default_factory=list)
    job_category: list[str] = field(default_factory=list)
    education: str | None = None
    sort_by: str | None = None
    salary_range: str | None = None  # "min-max", open ended allowed
    posted_within_days: int | None = None


def _parse_salary_range(salary_range: str) -> dict[str, int]:
    if "-" not in salary_range:
        return {}
    lo, hi = salary_range.split("-", 1)
    out: dict[str, int] = {}
    if lo.strip():
        try:
            out["salary_min"] = int(lo.strip())
        except ValueError:
            pass
    if hi.strip():
        try:
            out["salary_max"] = int(hi.strip())
        except ValueError:
            pass
    return out


def convert_params(p: JobSearchParams) -> dict[str, Any]:
    """Translate Chinese-language params into 104 API codes."""
    out: dict[str, Any] = {"keyword": p.keyword}

    area_codes = [AREA_MAP[a] for a in p.area if a in AREA_MAP]
    if area_codes:
        out["area"] = area_codes

    cat_codes = [JOB_TYPE_MAP[c] for c in p.job_category if c in JOB_TYPE_MAP]
    if cat_codes:
        out["job_category"] = cat_codes

    if p.education and p.education in EDUCATION_MAP:
        out["education"] = EDUCATION_MAP[p.education]

    if p.sort_by and p.sort_by in SORT_BY_MAP:
        out["sort_by"] = SORT_BY_MAP[p.sort_by]

    if p.salary_range:
        out.update(_parse_salary_range(p.salary_range))

    if p.posted_within_days:
        out["posted_within_days"] = p.posted_within_days

    return out


def _format_jobs(jobs: list[dict], max_show: int = 20) -> str:
    if not jobs:
        return "沒有找到符合條件的工作。"
    show = jobs[:max_show]
    lines = [f"找到 {len(jobs)} 筆，顯示前 {len(show)} 筆：\n"]
    for i, j in enumerate(show, 1):
        lines.append(f"{i}. {j.get('jobName', 'N/A')}")
        lines.append(f"   公司：{j.get('custName', 'N/A')}")
        lines.append(f"   地區：{j.get('jobAddrNoDesc', 'N/A')}")
        lo, hi = j.get("salaryLow", 0), j.get("salaryHigh", 0)
        if hi == 9999999:
            salary = f"{lo:,} 元以上"
        elif lo == 0 and hi == 0:
            salary = "待遇面議"
        else:
            salary = f"{lo:,} - {hi:,} 元"
        lines.append(f"   薪資：{salary}")
        link = (j.get("link") or {}).get("job", "N/A")
        lines.append(f"   連結：{link}")
        lines.append("")
    return "\n".join(lines)


async def search_104_jobs_impl(
    keyword: str,
    area: list[str] | None = None,
    job_category: list[str] | None = None,
    education: str | None = None,
    sort_by: str | None = None,
    salary_range: str | None = None,
    posted_within_days: int | None = None,
) -> dict[str, Any]:
    """Implementation backing the MCP tool. Returns structured dict for the agent."""
    params = JobSearchParams(
        keyword=keyword,
        area=area or [],
        job_category=job_category or [],
        education=education,
        sort_by=sort_by,
        salary_range=salary_range,
        posted_within_days=posted_within_days,
    )
    api_params = convert_params(params)
    jobs = search_104_jobs(**api_params)
    return {
        "total": len(jobs),
        "jobs": jobs[:20],
        "formatted": _format_jobs(jobs),
    }
