"""LLM Client Module."""

import json
import requests
from typing import Dict, Any, List, Optional
from ..config import config


def call_llm(
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict[str, Any]]] = None,
    api_key: Optional[str] = config.LLM_API_KEY,
    api_url: Optional[str] = config.LLM_API_URL,
    model: Optional[str] = config.LLM_MODEL or "gpt-5",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    stream: bool = False,
) -> Dict[str, Any]:
    """
    呼叫 LLM API（支援 OpenAI 格式）。

    Args:
        messages: 對話訊息列表
        tools: 工具定義列表（OpenAI function calling 格式）
        api_key: API 金鑰（預設從環境變數讀取）
        api_url: API 端點 URL（預設從環境變數讀取）
        model: 模型名稱（預設從環境變數讀取）
        temperature: 溫度參數（0.0-2.0）
        max_tokens: 最大 token 數量
        top_p: Top-p 採樣參數
        presence_penalty: Presence penalty 參數
        stream: 是否使用串流模式（預設 False）

    Returns:
        LLM 回應的字典

    Raises:
        ValueError: 當 API key 或 URL 未提供時
        requests.RequestException: 當 API 請求失敗時
    """
    if not api_key:
        raise ValueError(
            "API key is required. Please set LLM_API_KEY in .env file or pass it as a parameter."
        )
    if not api_url:
        raise ValueError(
            "API URL is required. Please set LLM_API_URL in .env file or pass it as a parameter."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }

    # 添加可選參數
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if top_p is not None:
        payload["top_p"] = top_p
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty

    # 如果提供了工具定義，加入到請求中
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Exception(f"Failed to call LLM API: {e}")


def extract_tool_calls(llm_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    從 LLM 回應中提取工具呼叫。

    Args:
        llm_response: LLM 的回應字典

    Returns:
        工具呼叫列表，每個包含 id, name, arguments
    """
    tool_calls = []

    choices = llm_response.get("choices", [])
    if not choices:
        return tool_calls

    message = choices[0].get("message", {})
    raw_tool_calls = message.get("tool_calls", [])

    for tool_call in raw_tool_calls:
        tool_calls.append({
            "id": tool_call.get("id"),
            "name": tool_call.get("function", {}).get("name"),
            "arguments": json.loads(tool_call.get("function", {}).get("arguments", "{}")),
        })

    return tool_calls
