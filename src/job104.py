"""104 Job Search Module."""

import requests
from typing import Optional, Union, List, Dict, Any

from mappings import (
    AREA_MAP,
    WORK_PERIOD_MAP,
    ROTATION_MAP,
    EXPERIENCE_MAP,
    EDUCATION_MAP,
    COMPANY_TYPE_MAP,
    WELFARE_MAP,
    SORT_BY_MAP,
    JOB_TYPE_MAP,
)


def search_104_jobs(
    keyword: Optional[str] = None,
    page: int = 1,
    keyword_in_job_title_only: bool = False,
    area: Optional[Union[str, List[str]]] = None,
    job_category: Optional[Union[str, List[str]]] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    work_period: Optional[Union[str, List[str]]] = None,
    rotation: Optional[str] = None,
    weekend_off: Optional[bool] = None,
    posted_within_days: Optional[int] = None,
    experience_years: Optional[str] = None,
    education: Optional[str] = None,
    company_type: Optional[Union[str, List[str]]] = None,
    welfare: Optional[List[str]] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> Dict[str, Any]:
    """
    搜尋 104 人力銀行的工作機會。

    Args:
        keyword: 搜尋關鍵字
        page: 頁數（預設為 1）
        keyword_in_job_title_only: 是否只搜尋職務名稱
        area: 地區（單一地區或多個地區列表）
        job_category: 職位類別（單一類別或多個類別列表）
        salary_min: 最低月薪（元）
        salary_max: 最高月薪（元）
        work_period: 上班時段（單一時段或多個時段列表）
        rotation: 輪班制度
        weekend_off: 是否週休二日
        posted_within_days: 發布天數內（0=本日、3=三日內、7=一週內、14=兩週內、30=一個月內）
        experience_years: 經歷要求
        education: 學歷要求
        company_type: 公司類型（單一類型或多個類型列表）
        welfare: 福利制度列表
        sort_by: 排序方式
        sort_order: 排序方向（"asc" 或 "desc"）

    Returns:
        包含工作機會資料的字典

    Raises:
        requests.RequestException: 當 API 請求失敗時
    """
    # API endpoint
    url = "https://www.104.com.tw/jobs/search/list"

    # 設置 headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.104.com.tw/jobs/search/",
    }

    # 建立查詢參數
    params: Dict[str, Any] = {}

    # 基礎參數
    if keyword:
        params["keyword"] = keyword
    params["page"] = page
    if keyword_in_job_title_only:
        params["kwop"] = "1"

    # 地區
    if area:
        areas = [area] if isinstance(area, str) else area
        area_codes = [AREA_MAP.get(a, a) for a in areas]
        params["area"] = ",".join(area_codes)

    # 職位類別
    if job_category:
        categories = [job_category] if isinstance(job_category, str) else job_category
        category_codes = [JOB_TYPE_MAP.get(c, c) for c in categories]
        params["jobcat"] = ",".join(category_codes)

    # 薪資範圍
    if salary_min is not None:
        params["scmin"] = salary_min
    if salary_max is not None:
        params["scmax"] = salary_max

    # 上班時段
    if work_period:
        periods = [work_period] if isinstance(work_period, str) else work_period
        period_codes = [WORK_PERIOD_MAP.get(p, p) for p in periods]
        # 需要將多個值相加（因為是 bitmask）
        if period_codes:
            total = sum(int(code) for code in period_codes)
            params["s9"] = str(total)

    # 輪班
    if rotation:
        params["s5"] = ROTATION_MAP.get(rotation, rotation)

    # 週休二日
    if weekend_off is not None:
        params["wktm"] = "1" if weekend_off else "0"

    # 更新日期
    if posted_within_days is not None:
        params["isnew"] = posted_within_days

    # 經歷要求
    if experience_years:
        params["jobexp"] = EXPERIENCE_MAP.get(experience_years, experience_years)

    # 學歷要求
    if education:
        params["edu"] = EDUCATION_MAP.get(education, education)

    # 公司類型
    if company_type:
        types = [company_type] if isinstance(company_type, str) else company_type
        type_codes = [COMPANY_TYPE_MAP.get(t, t) for t in types]
        params["zone"] = ",".join(type_codes)

    # 福利制度
    if welfare:
        welfare_codes = [WELFARE_MAP.get(w, w) for w in welfare]
        params["wf"] = ",".join(welfare_codes)

    # 排序
    if sort_by:
        params["order"] = SORT_BY_MAP.get(sort_by, sort_by)
    if sort_order:
        params["asc"] = "1" if sort_order == "asc" else "0"

    # 發送請求
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch job data from 104: {e}")
