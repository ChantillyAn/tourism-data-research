"""LLM 客户端 — 通过 requests 调用 OpenAI 兼容接口"""

from __future__ import annotations

import json
import logging

import requests

from src.config import get_llm_config

log = logging.getLogger(__name__)

_TIMEOUT = 60


def chat_completion(
    messages: list[dict[str, str]],
    model_override: str | None = None,
    temperature: float = 0.3,
) -> str:
    """调用 LLM chat completion，返回 assistant 回复文本

    Args:
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        model_override: 覆盖默认模型
        temperature: 温度参数

    Returns:
        模型回复的文本内容

    Raises:
        RuntimeError: API 调用失败
    """
    llm_config = get_llm_config()
    api_key = llm_config["api_key"]
    base_url = llm_config["base_url"].rstrip("/")
    model = model_override or llm_config["model"]

    url = f"{base_url}/chat/completions"

    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices")
        if not choices:
            raise RuntimeError(f"LLM 返回空结果: {json.dumps(data, ensure_ascii=False)[:200]}")

        content = choices[0]["message"]["content"]
        log.info("LLM 调用成功: model=%s", model)
        return content

    except requests.HTTPError as exc:
        body = exc.response.text[:500] if exc.response else ""
        log.error("LLM API 错误 (%s)", exc.response.status_code if exc.response else "?")
        raise RuntimeError(f"LLM API 错误 (HTTP {exc.response.status_code if exc.response else '?'})") from exc
    except requests.ConnectionError as exc:
        log.error("LLM 连接失败: %s", exc)
        raise RuntimeError(f"无法连接 LLM 服务: {base_url}") from exc
    except RuntimeError:
        raise
    except Exception as exc:
        log.error("LLM 调用异常: %s", exc)
        raise RuntimeError(f"LLM 调用失败: {exc}") from exc
