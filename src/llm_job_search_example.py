"""LLM Job Search Integration Example."""

import json
from typing import Dict, Any, List, Optional
from llm_client import call_llm, extract_tool_calls
from job_search_tool import (
    JOB_SEARCH_TOOL,
    execute_job_search_tool,
    format_job_search_results,
)


def chat_with_job_search(
    user_message: str,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    使用 LLM 進行工作搜尋對話。

    Args:
        user_message: 用戶的訊息
        api_key: LLM API 金鑰（預設從 .env 讀取）
        api_url: LLM API 端點（預設從 .env 讀取）
        model: 模型名稱（預設從 .env 讀取）

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
            "content": "你是一個專業的求職助手，幫助用戶在 104 人力銀行搜尋工作機會。當用戶描述他們想找的工作時，請使用 search_104_jobs 工具來搜尋，並將結果整理後回覆給用戶。",
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
    llm_response = call_llm(
        messages=messages,
        tools=tools,
        api_key=api_key,
        api_url=api_url,
        model=model,
    )

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
            search_result = execute_job_search_tool(tool_call["arguments"])

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

    # 第二次呼叫 LLM，讓它根據工具結果生成回應
    print("🤖 生成最終回應中...")
    final_response = call_llm(
        messages=messages,
        tools=tools,
        api_key=api_key,
        api_url=api_url,
        model=model,
    )

    # 記錄最終回應
    result["final_response"] = final_response["choices"][0]["message"]["content"]

    return result


def main():
    """
    主程式：示範如何使用 LLM 進行工作搜尋。

    注意：需要在 .env 文件中設定 LLM_API_KEY 和 LLM_API_URL
    """
    from config import config

    print("=" * 60)
    print("LLM 工作搜尋助手")
    print("=" * 60)
    print()

    # 檢查配置是否正確
    try:
        config.validate()
    except ValueError as e:
        print(f"⚠️  配置錯誤：{e}")
        print()
        print("使用方式：")
        print("1. 複製 .env_example 為 .env")
        print("2. 在 .env 中設定你的 API 金鑰和端點")
        print("3. 重新執行程式")
        print()
        return

    print(f"✓ 使用模型：{config.LLM_MODEL}")
    print(f"✓ API URL：{config.LLM_API_URL}")
    print()

    # 示範對話
    example_queries = [
        "我想找台北市的 Python 工程師工作，薪水至少 5 萬",
        "幫我找新北市的前端工程師，要大學以上學歷，一週內發布的職缺",
        "搜尋台北和新北的數據分析師工作，薪資 6-8 萬",
    ]

    for i, query in enumerate(example_queries, 1):
        print(f"\n{'=' * 60}")
        print(f"範例 {i}")
        print(f"{'=' * 60}")
        print(f"👤 用戶：{query}")
        print()

        try:
            # 使用 .env 中的預設設定
            result = chat_with_job_search(user_message=query)

            # 顯示工具呼叫記錄
            if result["has_tool_call"]:
                print("📝 工具呼叫記錄：")
                for idx, tool_call in enumerate(result["tool_calls"], 1):
                    print(f"   {idx}. {tool_call['tool_name']}")
                    print(f"      參數：{json.dumps(tool_call['parameters'], ensure_ascii=False, indent=6)}")
                print()

                print("📊 查詢結果摘要：")
                for idx, search_result in enumerate(result["search_results"], 1):
                    data = search_result.get("data", {})
                    total = data.get("totalCount", 0)
                    jobs_count = len(data.get("list", []))
                    print(f"   {idx}. 找到 {total:,} 筆工作，返回 {jobs_count} 筆")
                print()

            # 顯示最終回應
            print(f"🤖 助手：{result['final_response']}")

        except Exception as e:
            print(f"❌ 錯誤：{e}")

        print()


if __name__ == "__main__":
    main()
