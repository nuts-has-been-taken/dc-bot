"""Debug LLM API Request."""

import requests
import json
from config import config


def debug_api_request():
    """調試 API 請求以找出問題。"""
    print("=" * 60)
    print("調試 LLM API 請求")
    print("=" * 60)
    print()

    # 顯示配置
    print("配置資訊：")
    print(f"  - API URL: {config.LLM_API_URL}")
    print(f"  - Model: {config.LLM_MODEL}")
    print(f"  - API Key (前20字元): {config.LLM_API_KEY[:20] if config.LLM_API_KEY else 'None'}...")
    print()

    # 構建請求
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LLM_API_KEY}",
    }

    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "user", "content": "你好"}
        ],
    }

    print("請求資訊：")
    print(f"  - URL: {config.LLM_API_URL}")
    print(f"  - Headers: {json.dumps({k: v[:50] + '...' if len(v) > 50 else v for k, v in headers.items()}, indent=4, ensure_ascii=False)}")
    print(f"  - Payload: {json.dumps(payload, indent=4, ensure_ascii=False)}")
    print()

    # 發送請求
    print("發送請求...")
    try:
        response = requests.post(
            config.LLM_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        print(f"回應狀態碼: {response.status_code}")
        print()

        # 顯示回應 headers
        print("回應 Headers:")
        for key, value in response.headers.items():
            print(f"  - {key}: {value}")
        print()

        # 顯示回應內容
        print("回應內容:")
        print("-" * 60)
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2, ensure_ascii=False))
        except:
            print(response.text)
        print("-" * 60)
        print()

        if response.status_code == 200:
            print("✓ API 呼叫成功")
        else:
            print(f"✗ API 回傳錯誤狀態碼: {response.status_code}")

    except Exception as e:
        print(f"✗ 請求失敗: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    debug_api_request()
