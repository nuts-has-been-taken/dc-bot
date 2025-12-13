"""Job Search Tool for LLM."""

from typing import Dict, Any, Optional, List
from ..core.job104 import search_104_jobs
from ..core.mappings import AREA_MAP, JOB_TYPE_MAP, EDUCATION_MAP, SORT_BY_MAP

def convert_areas_to_codes(areas: List[str]) -> List[str]:
    """
    將地區名稱列表轉換為地區代碼列表。

    Args:
        areas: 地區名稱列表（如：["台北市", "新北市"]）

    Returns:
        地區代碼列表（如：["6001001000", "6001002000"]）
    """
    codes = []
    for area in areas:
        if area in AREA_MAP:
            codes.append(AREA_MAP[area])
        else:
            # 如果找不到對應代碼，記錄警告但繼續執行
            print(f"Warning: Area '{area}' not found in AREA_MAP, skipping...")
    return codes


def convert_job_categories_to_codes(categories: List[str]) -> List[str]:
    """
    將職位類別名稱列表轉換為職位類別代碼列表。

    Args:
        categories: 職位類別名稱列表（如：["軟體／工程類人員"]）

    Returns:
        職位類別代碼列表（如：["2007001000"]）
    """
    codes = []
    for category in categories:
        if category in JOB_TYPE_MAP:
            codes.append(JOB_TYPE_MAP[category])
        else:
            print(f"Warning: Job category '{category}' not found in JOB_TYPE_MAP, skipping...")
    return codes


def convert_education_to_code(education: str) -> Optional[str]:
    """
    將學歷名稱轉換為學歷代碼。

    Args:
        education: 學歷名稱（如："大學"）

    Returns:
        學歷代碼（如："4"），如果找不到則返回 None
    """
    if education in EDUCATION_MAP:
        return EDUCATION_MAP[education]
    else:
        print(f"Warning: Education '{education}' not found in EDUCATION_MAP")
        return None


def convert_sort_by_to_code(sort_by: str) -> Optional[str]:
    """
    將排序方式名稱轉換為排序代碼。

    Args:
        sort_by: 排序方式名稱（如："符合度"）

    Returns:
        排序代碼（如："1"），如果找不到則返回 None
    """
    if sort_by in SORT_BY_MAP:
        return SORT_BY_MAP[sort_by]
    else:
        print(f"Warning: Sort by '{sort_by}' not found in SORT_BY_MAP")
        return None


def parse_salary_range(salary_range: str) -> Dict[str, Optional[int]]:
    """
    解析薪資範圍字串。

    Args:
        salary_range: 薪資範圍字串，格式：'最低-最高'

    Returns:
        包含 salary_min 和 salary_max 的字典

    Examples:
        >>> parse_salary_range('40000-60000')
        {'salary_min': 40000, 'salary_max': 60000}
        >>> parse_salary_range('40000-')
        {'salary_min': 40000, 'salary_max': None}
        >>> parse_salary_range('-60000')
        {'salary_min': None, 'salary_max': 60000}
    """
    result = {"salary_min": None, "salary_max": None}

    if not salary_range or "-" not in salary_range:
        return result

    parts = salary_range.split("-")
    if len(parts) != 2:
        return result

    min_str, max_str = parts

    if min_str.strip():
        try:
            result["salary_min"] = int(min_str.strip())
        except ValueError:
            pass

    if max_str.strip():
        try:
            result["salary_max"] = int(max_str.strip())
        except ValueError:
            pass

    return result


def convert_tool_params_to_search_params(tool_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    將簡化的工具參數轉換為完整的搜尋參數。
    會將文字參數（地區、職位類別、學歷、排序方式）轉換為對應的代碼。

    Args:
        tool_params: 從 LLM 工具呼叫中獲得的參數

    Returns:
        可以直接傳入 search_104_jobs 的參數字典
    """
    search_params = {}

    # 直接傳遞的參數（不需要轉換）
    if "keyword" in tool_params:
        search_params["keyword"] = tool_params["keyword"]

    if "posted_within_days" in tool_params:
        search_params["posted_within_days"] = tool_params["posted_within_days"]

    # 需要轉換為代碼的參數
    if "area" in tool_params:
        area_codes = convert_areas_to_codes(tool_params["area"])
        if area_codes:
            search_params["area"] = area_codes

    if "job_category" in tool_params:
        category_codes = convert_job_categories_to_codes(tool_params["job_category"])
        if category_codes:
            search_params["job_category"] = category_codes

    if "education" in tool_params:
        education_code = convert_education_to_code(tool_params["education"])
        if education_code:
            search_params["education"] = education_code

    if "sort_by" in tool_params:
        sort_code = convert_sort_by_to_code(tool_params["sort_by"])
        if sort_code:
            search_params["sort_by"] = sort_code

    # 薪資範圍參數轉換
    if "salary_range" in tool_params:
        salary_info = parse_salary_range(tool_params["salary_range"])
        if salary_info["salary_min"] is not None:
            search_params["salary_min"] = salary_info["salary_min"]
        if salary_info["salary_max"] is not None:
            search_params["salary_max"] = salary_info["salary_max"]

    return search_params


def execute_job_search_tool(tool_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    執行工作搜尋工具。

    Args:
        tool_params: 從 LLM 工具呼叫中獲得的參數

    Returns:
        搜尋結果

    Raises:
        Exception: 當搜尋失敗時
    """
    # 轉換參數
    search_params = convert_tool_params_to_search_params(tool_params)

    # 執行搜尋
    try:
        result = search_104_jobs(**search_params)
        return result
    except Exception as e:
        raise Exception(f"Failed to execute job search: {e}")


def format_job_search_results(result: list, max_jobs: int = 100) -> str:
    """
    格式化工作搜尋結果為易讀的文字。

    Args:
        result: search_104_jobs 的回應
        max_jobs: 最多顯示幾筆工作

    Returns:
        格式化的文字結果
    """

    total = len(result)

    if total == 0:
        return "沒有找到符合條件的工作。"

    # 限制顯示數量
    jobs_to_show = result[:max_jobs]

    lines = [f"找到 {total:,} 筆工作，以下是前 {len(jobs_to_show)} 筆：\n"]

    for i, job in enumerate(jobs_to_show, 0):
        lines.append(f"{i}. {job.get('jobName', 'N/A')}")
        lines.append(f"   公司：{job.get('custName', 'N/A')}")
        lines.append(f"   地區：{job.get('jobAddrNoDesc', 'N/A')}")
        if job.get('salaryHigh')==9999999:
            salary_desc = f"{job.get('salaryLow', 'N/A')} 元以上"
        elif job.get('salaryHigh')==0 and job.get('salaryLow')==0:
            salary_desc = "待遇面議"
        else:
            salary_desc = f"{job.get('salaryLow', 'N/A')} - {job.get('salaryHigh', 'N/A')} 元"
        lines.append(f"   薪資：{salary_desc}")
        
        education_key = next((key for key, value in EDUCATION_MAP.items() if value == job.get('optionEdu')[0]), 'N/A')
        lines.append(f"   學歷：{education_key}")
        lines.append(f"   經歷：{job.get('period', 'N/A')}年")
        lines.append(f"   更新：{job.get('appearDate', 'N/A')}")
        if job.get('link'):
            lines.append(f"   連結：{job.get('link').get('job', 'N/A')}")
        else:
            lines.append("   連結：N/A")
        lines.append(f"   介紹：{job.get('description', 'N/A')[:100]}...")
        lines.append("")

    return "\n".join(lines)
