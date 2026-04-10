from __future__ import annotations

import requests


# Ollama 服务的本地地址，默认跑在 11434 端口。
OLLAMA_BASE_URL = "http://localhost:11434"


def generate_reply(model: str, messages: list[dict[str, str]]) -> str:
    """
    直接通过 HTTP 调用 Ollama REST API 获取大模型回复。
    绕过 ollama Python 库 0.6.x 版本的 502 兼容问题。
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"

    payload = {
        "model": model,
        "messages": messages,
        # stream=False：让 Ollama 一次性返回完整 JSON，不分段推送。
        "stream": False,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=120,
            # 关键修复！强制绕过系统 HTTP 代理设置。
            # Windows 上如果配置了 VPN 或上网代理， requests 会把请求发给代理服务器，
            # 代理当然找不到 localhost，于是返回 502 Bad Gateway。
            # 传入 {"http": None, "https": None} 可以强制绕过代理直连本地。
            proxies={"http": None, "https": None},
        )
        response.raise_for_status()  # 状态码非 2xx 时抛出异常
        data = response.json()
        # 从返回的 JSON 里取出 message.content 字段
        return str(data.get("message", {}).get("content", "")).strip()

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接 Ollama，请确认已运行 'ollama serve'")
        return ""
    except requests.exceptions.Timeout:
        print("❌ Ollama 响应超时（超过 120 秒）")
        return ""
    except Exception as e:
        print(f"❌ 大模型调用失败: {e}")
        return ""
