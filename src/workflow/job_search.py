"""LLM Job Search Integration Example."""

import json
import re
import time
from typing import Dict, Any, Optional
from ..llm.client import call_llm
from ..llm.tools import (
    execute_job_search_tool,
    format_job_search_results,
)
from .prompt import (
    JOB_SEARCH_FINAL_RESPONSE_PROMPT,
    JOB_SEARCH_EXTRACT_PARAMS_PROMPT,
)


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    從文字中提取 JSON，處理可能的 markdown 代碼塊包裝。

    Args:
        text: 包含 JSON 的文字

    Returns:
        解析後的 JSON 字典，如果失敗則返回 None
    """
    # 嘗試直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 嘗試提取 markdown 代碼塊中的 JSON
    json_pattern = r"```(?:json)?\s*(\{[\s\S]*?\})\s*```"
    matches = re.findall(json_pattern, text)

    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass

    # 嘗試找到第一個完整的 JSON 物件
    brace_pattern = r"\{[\s\S]*\}"
    matches = re.findall(brace_pattern, text)

    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    return None


def chat_with_job_search(
    user_message: str
) -> Dict[str, Any]:
    """
    使用 LLM 進行工作搜尋對話（使用文字解析，不使用 tool calling）。

    Args:
        user_message: 用戶的訊息

    Returns:
        包含完整記錄的字典：
        {
            "user_message": str,              # 用戶訊息
            "search_params": Dict,            # 搜尋參數
            "search_results": List[Dict],     # 搜尋結果
            "final_response": str,            # LLM 最終回應
            "need_search": bool,              # 是否需要搜尋
        }

    Example:
        >>> # 使用 .env 中的設定
        >>> result = chat_with_job_search(
        ...     "我想找台北市的 Python 工程師工作，薪水至少 5 萬"
        ... )
        >>> print(result["final_response"])
    """
    # 準備返回結果
    result = {
        "user_message": user_message,
        "search_params": {},
        "search_results": [],
        "final_response": "",
        "need_search": False,
    }

    # 第一步：使用 LLM 提取搜尋參數
    print("🤖 分析用戶需求中...")
    messages = [
        {
            "role": "system",
            "content": JOB_SEARCH_EXTRACT_PARAMS_PROMPT,
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    start_time = time.time()
    llm_response = call_llm(messages=messages)
    llm_time = time.time() - start_time

    # 顯示第一次 LLM 呼叫的時間和 token 使用量
    print(f"⏱️  參數提取耗時: {llm_time:.2f} 秒")
    if "usage" in llm_response:
        usage = llm_response["usage"]
        print(f"📊 Token 使用量: {usage.get('total_tokens', 0)} tokens "
              f"(prompt: {usage.get('prompt_tokens', 0)}, "
              f"completion: {usage.get('completion_tokens', 0)})")

    # 提取 LLM 回應內容
    response_text = llm_response["choices"][0]["message"]["content"]
    print(f"📝 LLM 回應：{response_text}")

    # 解析 JSON
    parsed_json = extract_json_from_text(response_text)

    if not parsed_json:
        # 無法解析 JSON，直接返回 LLM 的回應
        print("⚠️  無法解析 JSON，直接返回 LLM 回應")
        result["final_response"] = response_text
        return result

    # 檢查是否需要搜尋
    need_search = parsed_json.get("need_search", False)
    result["need_search"] = need_search

    if not need_search:
        # 不需要搜尋，直接返回訊息
        result["final_response"] = parsed_json.get("message", response_text)
        return result

    # 需要搜尋，提取參數
    search_params = parsed_json.get("params", {})
    result["search_params"] = search_params

    # 執行工作搜尋
    print("🕷️  執行 104 工作搜尋...")
    crawler_start_time = time.time()
    try:
        search_result = execute_job_search_tool(search_params)
        crawler_time = time.time() - crawler_start_time
        print(f"⏱️  爬蟲執行耗時: {crawler_time:.2f} 秒")

        result["search_results"].append(search_result)

        # 格式化結果
        formatted_result = format_job_search_results(search_result)

    except Exception as e:
        print(f"❌ 搜尋失敗：{e}")
        result["final_response"] = f"搜尋時發生錯誤：{str(e)}"
        return result

    # 第二步：讓 LLM 根據搜尋結果生成最終回應
    print("🤖 生成最終回應中...")
    final_messages = [
        {
            "role": "system",
            "content": JOB_SEARCH_FINAL_RESPONSE_PROMPT,
        },
        {
            "role": "user",
            "content": f"用戶需求：{user_message}\n\n搜尋結果：\n{formatted_result}",
        },
    ]

    final_start_time = time.time()
    final_response = call_llm(messages=final_messages)
    final_llm_time = time.time() - final_start_time
    # 顯示第二次 LLM 呼叫的時間和 token 使用量
    print(f"⏱️  最終回應生成耗時: {final_llm_time:.2f} 秒")
    if "usage" in final_response:
        usage = final_response["usage"]
        print(f"📊 Token 使用量: {usage.get('total_tokens', 0)} tokens "
              f"(prompt: {usage.get('prompt_tokens', 0)}, "
              f"completion: {usage.get('completion_tokens', 0)})")

    # 記錄最終回應
    result["final_response"] = final_response["choices"][0]["message"]["content"]
    print(f"📝 最終回應長度：{len(result['final_response'])} 字元")
    return result
