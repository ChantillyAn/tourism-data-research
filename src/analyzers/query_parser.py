"""查询解析 — 使用 LLM 将自然语言查询转为搜索策略"""

from __future__ import annotations

import logging
from pathlib import Path

from src.llm_client import chat_completion
from src.utils.json_extract import extract_json_from_llm

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "query_parse.txt"


def parse_query(query: str, model_override: str | None = None) -> dict:
    """解析用户查询，返回结构化搜索策略

    Returns:
        dict with keys: intent, region, time_range, topics, search_queries, data_focus
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    try:
        content = chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            model_override=model_override,
        )

        parsed = extract_json_from_llm(content.strip())

        log.info("查询解析完成: %d 个搜索查询", len(parsed.get("search_queries", [])))
        return parsed

    except Exception as exc:
        log.error("查询解析失败: %s", exc)
        # 降级：直接用原始查询作为搜索
        return {
            "intent": query,
            "region": None,
            "time_range": None,
            "topics": [],
            "search_queries": [query],
            "data_focus": [],
        }
