"""日报 Markdown 渲染"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from jinja2 import Environment, FileSystemLoader

from src.config import (
    DAILY_MAX_DATA_POINTS,
    DAILY_MAX_HOT_TOPICS,
    DAILY_MAX_POLICIES,
    TEMPLATES_DIR,
)

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_daily(items: Sequence[dict], target_date: date | None = None) -> str:
    """将已分类条目渲染为日报 Markdown"""
    d = target_date or date.today()

    policies = [i for i in items if i["category"] == "政策动态"][:DAILY_MAX_POLICIES]
    data_points = [i for i in items if i["category"] == "数据快报"][:DAILY_MAX_DATA_POINTS]
    hot_topics = [i for i in items if i["category"] == "行业热点"][:DAILY_MAX_HOT_TOPICS]

    template = _env.get_template("daily.md.j2")
    return template.render(
        date=d.strftime("%Y年%m月%d日"),
        policies=policies,
        data_points=data_points,
        hot_topics=hot_topics,
    )
