"""JSON 提取工具"""

from __future__ import annotations

import json


def extract_json_from_llm(text: str) -> dict:
    """从 LLM 响应中提取 JSON（兼容直接 JSON 和 markdown 代码块）"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 ```json ... ``` 代码块提取
    if "```json" in text:
        try:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return json.loads(text[start:end].strip())
        except (ValueError, json.JSONDecodeError):
            pass

    # 尝试从 ``` ... ``` 代码块提取
    if "```" in text:
        try:
            start = text.index("```") + 3
            # 跳过可能的语言标识行
            newline = text.index("\n", start)
            end = text.index("```", newline)
            return json.loads(text[newline:end].strip())
        except (ValueError, json.JSONDecodeError):
            pass

    raise ValueError(f"无法从 LLM 响应中提取 JSON: {text[:200]}")
