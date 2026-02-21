"""Markdown 报告渲染"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.config import REPORTS_DIR, RESEARCH_TEMPLATES_DIR

log = logging.getLogger(__name__)

_env = Environment(
    loader=FileSystemLoader(str(RESEARCH_TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_report(analysis: dict, query: str, output_dir: Path | None = None) -> Path:
    """渲染研究报告为 Markdown 文件

    Args:
        analysis: LLM 分析结果（title, summary, sections, charts, sources, limitations）
        query: 原始查询
        output_dir: 输出目录（默认为 data/reports/{date}_{slug}/）

    Returns:
        报告文件路径
    """
    if output_dir is None:
        slug = _make_slug(query)
        dir_name = f"{datetime.now().strftime('%Y-%m-%d')}_{slug}"
        output_dir = REPORTS_DIR / dir_name

    output_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(exist_ok=True)

    template = _env.get_template("report.md.j2")
    markdown = template.render(
        title=analysis.get("title", f"研究报告：{query}"),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        query=query,
        summary=analysis.get("summary", ""),
        sections=analysis.get("sections", []),
        charts=analysis.get("charts", []),
        sources=analysis.get("sources", []),
        limitations=analysis.get("limitations", ""),
    )

    report_path = output_dir / "report.md"
    report_path.write_text(markdown, encoding="utf-8")
    log.info("报告已保存: %s", report_path)

    return report_path


def _make_slug(query: str, max_len: int = 30) -> str:
    """从查询生成文件名安全的 slug"""
    # 保留中文和字母数字，其他替换为下划线
    slug = ""
    for ch in query:
        if ch.isalnum() or ch in ("_", "-") or "\u4e00" <= ch <= "\u9fff":
            slug += ch
        elif slug and slug[-1] != "_":
            slug += "_"

    return slug[:max_len].strip("_") or "research"
