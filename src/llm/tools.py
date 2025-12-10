"""Job Search Tool for LLM."""

from typing import Dict, Any, Optional, List
from ..core.job104 import search_104_jobs
from ..core.mappings import AREA_MAP, JOB_TYPE_MAP, EDUCATION_MAP, SORT_BY_MAP


# 工具定義（OpenAI function calling 格式）
JOB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_104_jobs",
        "description": "搜尋 104 人力銀行的工作機會。可以根據關鍵字、地區、職位類別、薪資範圍、學歷要求、發布時間等條件進行篩選。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜尋關鍵字，例如：Python、前端工程師、數據分析師",
                },
                "area": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "工作地區，可以是多個。支援全台灣所有縣市，且台北市、新北市支援區級地區（如：台北市大安區、新北市板橋區）。"
                        "例如：['台北市', '新北市']、['台北市大安區', '台北市信義區']、['台中市', '高雄市']"
                    ),
                },
                "job_category": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "職位類別，可以是多個。可選擇的類別包括：\n"
                        "經營管理：經營／幕僚類人員、人力資源類人員\n"
                        "行政法務：行政／總務類人員、法務／智財類人員\n"
                        "金融財會：金融專業相關類人員、財務／會計／稅務類\n"
                        "行銷企劃：行銷類人員、產品企劃類人員、專案／產品管理類人員\n"
                        "業務客服：客戶服務類人員、門市營業類人員、業務銷售類人員、貿易類人員\n"
                        "餐飲旅遊：餐飲類人員、旅遊休閒類人員、美容／美髮類人員\n"
                        "資訊科技：軟體／工程類人員、MIS／網管類人員\n"
                        "技術維修：操作／技術類人員、維修／技術服務類人員\n"
                        "物流採購：採購／資材／倉管類人員、運輸物流類人員\n"
                        "營建工程：營建規劃類人員、營建施作類人員、製圖／測量類人員\n"
                        "設計藝術：設計類人員、傳播藝術類人員\n"
                        "文編媒體：文字編譯類人員、記者及採訪類人員\n"
                        "醫療保健：醫療專業類人員、醫療／保健服務人員\n"
                        "教育研究：學術研究類人員、教育輔導類人員\n"
                        "研發創新：工程研發類人員、化工材料研發類人員、生技／醫療研發類人員\n"
                        "生產製造：生產管理類人員、製程規劃類人員、品保／品管類人員、環境安全衛生類人員\n"
                        "安全保全：軍警消防類人員、保全類人員\n"
                        "其他：農林漁牧相關類人員、其他類人員"
                    ),
                },
                "salary_range": {
                    "type": "string",
                    "description": "薪資範圍，格式：'最低-最高'（單位：元）。例如：'40000-60000' 表示 4 萬到 6 萬元。如果只有最低薪資，格式為：'40000-'；只有最高薪資，格式為：'-60000'",
                },
                "education": {
                    "type": "string",
                    "description": "學歷要求。選項：高中職以下、高中職、專科、大學、碩士、博士",
                },
                "posted_within_days": {
                    "type": "integer",
                    "description": "發布天數內的工作。例如：7 表示過去 7 天內發布的工作",
                },
                "sort_by": {
                    "type": "string",
                    "description": "排序方式。選項：符合度、日期、經歷、學歷、應徵人數、待遇",
                },
            },
            "required": [],
        },
    },
}


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


def format_job_search_results(result: Dict[str, Any], max_jobs: int = 100) -> str:
    """
    格式化工作搜尋結果為易讀的文字。

    Args:
        result: search_104_jobs 的回應
        max_jobs: 最多顯示幾筆工作

    Returns:
        格式化的文字結果
    """
    if result.get("status") != 200:
        return f"搜尋失敗：{result.get('errorMsg', '未知錯誤')}"

    data = result.get("data", {})
    jobs = data.get("list", [])
    total = data.get("totalCount", 0)

    if total == 0:
        return "沒有找到符合條件的工作。"

    # 限制顯示數量
    jobs_to_show = jobs[:max_jobs]

    lines = [f"找到 {total:,} 筆工作，以下是前 {len(jobs_to_show)} 筆：\n"]

    for i, job in enumerate(jobs_to_show, 0):
        lines.append(f"{i}. {job.get('jobName', 'N/A')}")
        lines.append(f"   公司：{job.get('custName', 'N/A')}")
        lines.append(f"   地區：{job.get('jobAddrNoDesc', 'N/A')}")
        lines.append(f"   薪資：{job.get('salaryDesc', 'N/A')}")
        lines.append(f"   學歷：{job.get('optionEdu', 'N/A')}")
        lines.append(f"   經歷：{job.get('periodDesc', 'N/A')}")
        lines.append(f"   更新：{job.get('appearDateDesc', 'N/A')}")
        lines.append(f"   連結：https://www.104.com.tw/job/{job.get('jobNo', '')}")
        lines.append(f"   介紹：{job.get('description', 'N/A')[:100]}...")
        lines.append("")

    return "\n".join(lines)
