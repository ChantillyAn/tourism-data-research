"""数据分析 — 使用 LLM 分析搜索结果并生成结构化报告"""

from __future__ import annotations

import logging
from pathlib import Path

from src.llm_client import chat_completion
from src.utils.json_extract import extract_json_from_llm

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "analyze.txt"


def analyze_data(
    query: str,
    search_strategy: dict,
    contents: list[dict],
    model_override: str | None = None,
) -> dict:
    """分析搜索结果，返回结构化报告数据

    Args:
        query: 用户原始查询
        search_strategy: 查询解析结果
        contents: 提取的网页内容列表 [{url, title, text}]
        model_override: 可选的模型覆盖

    Returns:
        dict with keys: title, summary, sections, charts, sources, limitations
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    user_message = _build_user_message(query, search_strategy, contents)

    try:
        content = chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model_override=model_override,
        )

        parsed = extract_json_from_llm(content.strip())

        log.info(
            "数据分析完成: %d 个章节, %d 个图表",
            len(parsed.get("sections", [])),
            len(parsed.get("charts", [])),
        )
        return parsed

    except Exception as exc:
        log.error("数据分析失败: %s", exc)
        return {
            "title": f"研究报告：{query}",
            "summary": f"分析过程中出现错误: {exc}",
            "sections": [],
            "charts": [],
            "sources": [],
            "limitations": f"分析失败: {exc}",
        }


def _build_user_message(query: str, strategy: dict, contents: list[dict]) -> str:
    """构建提交给分析 LLM 的用户消息"""
    parts = [
        f"## 研究查询\n{query}\n",
        f"## 查询解析\n- 意图: {strategy.get('intent', '')}\n"
        f"- 地区: {strategy.get('region', '未指定')}\n"
        f"- 时间: {strategy.get('time_range', '未指定')}\n"
        f"- 数据关注: {', '.join(strategy.get('data_focus', []))}\n",
        "## 搜索结果与网页内容\n",
    ]

    if not contents:
        parts.append("（未获取到有效内容）\n")
    else:
        for i, item in enumerate(contents, 1):
            text = item.get("text", "")
            # 截断过长内容，留给 LLM 上下文窗口
            if len(text) > 2000:
                text = text[:2000] + "...(截断)"
            parts.append(
                f"### 来源 {i}: {item.get('title', '未知')}\n"
                f"URL: {item.get('url', '')}\n"
                f"内容:\n{text}\n\n"
            )

    return "\n".join(parts)
