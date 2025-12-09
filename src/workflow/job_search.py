"""LLM Job Search Integration Example."""

import json
import time
from typing import Dict, Any
from ..llm.client import call_llm, extract_tool_calls
from ..llm.tools import (
    JOB_SEARCH_TOOL,
    execute_job_search_tool,
    format_job_search_results,
)
from .prompt import JOB_SEARCH_FINAL_RESPONSE_PROMPT


def chat_with_job_search(
    user_message: str
) -> Dict[str, Any]:
    """
    使用 LLM 進行工作搜尋對話。

    Args:
        user_message: 用戶的訊息

    Returns:
        包含完整記錄的字典：
        {
            "user_message": str,              # 用戶訊息
            "tool_calls": List[Dict],         # 工具呼叫記錄
            "search_results": List[Dict],     # 搜尋結果
            "final_response": str,            # LLM 最終回應
            "has_tool_call": bool,            # 是否使用了工具
        }

    Example:
        >>> # 使用 .env 中的設定
        >>> result = chat_with_job_search(
        ...     "我想找台北市的 Python 工程師工作，薪水至少 5 萬"
        ... )
        >>> print(result["final_response"])
        >>> print(result["tool_calls"])
    """
    # 準備返回結果
    result = {
        "user_message": user_message,
        "tool_calls": [],
        "search_results": [],
        "final_response": "",
        "has_tool_call": False,
    }

    # 準備對話訊息
    messages = [
        {
            "role": "system",
            "content": "你是一個專業的求職助手，幫助用戶在 104 人力銀行搜尋工作機會。當用戶描述他們想找的工作時，請使用 search_104_jobs 工具來搜尋",
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    # 準備工具定義
    tools = [JOB_SEARCH_TOOL]

    # 第一次呼叫 LLM
    print("🤖 呼叫 LLM 中...")
    start_time = time.time()
    llm_response = call_llm(
        messages=messages,
        tools=tools,
    )
    llm_time = time.time() - start_time

    # 顯示第一次 LLM 呼叫的時間和 token 使用量
    print(f"⏱️  第一次 LLM 呼叫耗時: {llm_time:.2f} 秒")
    if "usage" in llm_response:
        usage = llm_response["usage"]
        print(f"📊 Token 使用量: {usage.get('total_tokens', 0)} tokens "
              f"(prompt: {usage.get('prompt_tokens', 0)}, "
              f"completion: {usage.get('completion_tokens', 0)})")

    # 檢查是否有工具呼叫
    tool_calls = extract_tool_calls(llm_response)

    if not tool_calls:
        # 沒有工具呼叫，直接返回 LLM 的回應
        result["final_response"] = llm_response["choices"][0]["message"]["content"]
        return result

    # 執行工具呼叫
    result["has_tool_call"] = True
    print(f"🔧 執行工具呼叫：{len(tool_calls)} 個")

    for tool_call in tool_calls:
        if tool_call["name"] == "search_104_jobs":
            print(f"   參數：{json.dumps(tool_call['arguments'], ensure_ascii=False, indent=2)}")

            # 記錄工具輸入參數
            tool_call_record = {
                "tool_name": tool_call["name"],
                "parameters": tool_call["arguments"],
            }
            result["tool_calls"].append(tool_call_record)

            # 執行工作搜尋
            print("🕷️  執行 104 工作搜尋...")
            crawler_start_time = time.time()
            search_result = execute_job_search_tool(tool_call["arguments"])
            crawler_time = time.time() - crawler_start_time
            print(f"⏱️  爬蟲執行耗時: {crawler_time:.2f} 秒")

            # 記錄查詢結果
            result["search_results"].append(search_result)

            # 格式化結果
            formatted_result = format_job_search_results(search_result)

            # 將工具執行結果加入對話
            messages.append(llm_response["choices"][0]["message"])
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": tool_call["name"],
                "content": formatted_result,
            })
    
    # 指導 LLM 生成最終回應
    messages.append({
        "role": "system",
        "content": JOB_SEARCH_FINAL_RESPONSE_PROMPT,
    })

    # 第二次呼叫 LLM，讓它根據工具結果生成回應
    print("🤖 生成最終回應中...")
    final_start_time = time.time()
    final_response = call_llm(
        messages=messages,
    )
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

    return result
