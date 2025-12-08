"""LLM Job Search Integration Example."""

import json
from llm_client import call_llm, extract_tool_calls
from job_search_tool import (
    JOB_SEARCH_TOOL,
    execute_job_search_tool,
    format_job_search_results,
)


def chat_with_job_search(
    user_message: str,
    api_key: str,
    api_url: str,
    model: str = "gpt-4",
) -> str:
    """
    使用 LLM 進行工作搜尋對話。

    Args:
        user_message: 用戶的訊息
        api_key: LLM API 金鑰
        api_url: LLM API 端點
        model: 模型名稱

    Returns:
        LLM 的回應文字

    Example:
        >>> response = chat_with_job_search(
        ...     "我想找台北市的 Python 工程師工作，薪水至少 5 萬",
        ...     api_key="your-api-key",
        ...     api_url="https://api.openai.com/v1/chat/completions"
        ... )
    """
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
        return llm_response["choices"][0]["message"]["content"]

    # 執行工具呼叫
    print(f"🔧 執行工具呼叫：{len(tool_calls)} 個")

    for tool_call in tool_calls:
        if tool_call["name"] == "search_104_jobs":
            print(f"   參數：{json.dumps(tool_call['arguments'], ensure_ascii=False, indent=2)}")

            # 執行工作搜尋
            search_result = execute_job_search_tool(tool_call["arguments"])

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

    return final_response["choices"][0]["message"]["content"]


def main():
    """
    主程式：示範如何使用 LLM 進行工作搜尋。

    注意：需要設定環境變數或直接提供 API_KEY 和 API_URL
    """
    print("=" * 60)
    print("LLM 工作搜尋助手")
    print("=" * 60)
    print()

    # TODO: 設定你的 API 金鑰和端點
    API_KEY = "your-api-key-here"
    API_URL = "https://api.openai.com/v1/chat/completions"
    MODEL = "gpt-4"

    if API_KEY == "your-api-key-here":
        print("⚠️  請先設定 API_KEY 和 API_URL")
        print()
        print("使用方式：")
        print("1. 在程式中設定 API_KEY 和 API_URL")
        print("2. 或使用環境變數：")
        print("   export OPENAI_API_KEY='your-key'")
        print("   export OPENAI_API_URL='your-url'")
        print()
        return

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
            response = chat_with_job_search(
                user_message=query,
                api_key=API_KEY,
                api_url=API_URL,
                model=MODEL,
            )
            print(f"🤖 助手：{response}")
        except Exception as e:
            print(f"❌ 錯誤：{e}")

        print()


if __name__ == "__main__":
    main()
