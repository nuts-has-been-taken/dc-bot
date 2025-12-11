"""Job Detail Analysis Workflow."""

import time
from typing import Dict, Any
from ..llm.client import call_llm
from .prompt import JOB_DETAIL_ANALYSIS_PROMPT


def analyze_job_detail(job_query: str) -> Dict[str, Any]:
    """
    使用 LLM 分析特定職缺的詳細資訊。

    此函數利用 LLM 內建的 web search 功能，查詢職缺相關的公司背景、
    職位要求、員工評價等資訊，並生成分析報告。

    Args:
        job_query: 職缺查詢資訊，應包含職位名稱、公司名稱等基本描述。
                  範例：「某科技公司的 Python 後端工程師」或
                        「104 職缺連結：https://www.104.com.tw/job/xxxxx」

    Returns:
        包含分析結果的字典：
        {
            "job_query": str,                # 輸入的職缺查詢
            "analysis_report": str,          # LLM 生成的分析報告
            "processing_time": float,        # 處理時間（秒）
            "token_usage": Dict,             # Token 使用量統計
        }

    Example:
        >>> result = analyze_job_detail("某科技公司的 Python 後端工程師")
        >>> print(result["analysis_report"])

        >>> # 也可以直接傳入 104 連結
        >>> result = analyze_job_detail("https://www.104.com.tw/job/xxxxx")
        >>> print(result["analysis_report"])
    """

    # 準備返回結果
    result = {
        "job_query": job_query,
        "analysis_report": "",
        "processing_time": 0.0,
        "token_usage": {},
    }

    # 使用 LLM 進行分析
    print("🤖 分析職缺詳細資訊中...")

    messages = [
        {
            "role": "system",
            "content": JOB_DETAIL_ANALYSIS_PROMPT.format(job_info=job_query),
        },
        {
            "role": "user",
            "content": "請開始分析這個職缺。",
        },
    ]

    start_time = time.time()
    llm_response = call_llm(messages=messages)
    processing_time = time.time() - start_time

    result["processing_time"] = processing_time

    # 顯示處理時間和 token 使用量
    print(f"⏱️  分析耗時: {processing_time:.2f} 秒")
    if "usage" in llm_response:
        usage = llm_response["usage"]
        result["token_usage"] = {
            "total": usage.get("total_tokens", 0),
            "prompt": usage.get("prompt_tokens", 0),
            "completion": usage.get("completion_tokens", 0),
        }
        print(f"📊 Token 使用量: {usage.get('total_tokens', 0)} tokens "
              f"(prompt: {usage.get('prompt_tokens', 0)}, "
              f"completion: {usage.get('completion_tokens', 0)})")

    # 提取分析報告
    result["analysis_report"] = llm_response["choices"][0]["message"]["content"]
    print(f"📝 報告長度：{len(result['analysis_report'])} 字元")

    return result
