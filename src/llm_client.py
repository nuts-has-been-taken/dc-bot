"""LLM Client Module."""

import json
import requests
from typing import Dict, Any, List, Optional


def call_llm(
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict[str, Any]]] = None,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    model: str = "gpt-4",
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    呼叫 LLM API（支援 OpenAI 格式）。

    Args:
        messages: 對話訊息列表
        tools: 工具定義列表（OpenAI function calling 格式）
        api_key: API 金鑰
        api_url: API 端點 URL
        model: 模型名稱
        temperature: 溫度參數

    Returns:
        LLM 回應的字典

    Raises:
        ValueError: 當 API key 或 URL 未提供時
        requests.RequestException: 當 API 請求失敗時
    """
    if not api_key:
        raise ValueError("API key is required")
    if not api_url:
        raise ValueError("API URL is required")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    # 如果提供了工具定義，加入到請求中
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30,
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
