"""去重：基于标题和 URL 对比已处理条目"""

from __future__ import annotations

import logging
import sqlite3
from typing import Sequence

from src.collectors.rss import FeedItem
from src.db.models import get_recent_titles, get_recent_urls

log = logging.getLogger(__name__)


def filter_new(items: Sequence[FeedItem], conn: sqlite3.Connection) -> list[FeedItem]:
    """过滤掉最近已报道过的条目，返回新条目列表"""
    seen_titles = get_recent_titles(conn)
    seen_urls = get_recent_urls(conn)

    new_items: list[FeedItem] = []
    for item in items:
        if not item.title:
            continue
        if item.title in seen_titles:
            log.debug("去重(标题): %s", item.title)
            continue
        if item.url and item.url in seen_urls:
            log.debug("去重(URL): %s", item.url)
            continue
        new_items.append(item)

    removed = len(items) - len(new_items)
    if removed > 0:
        log.info("去重: %d 条已报道，%d 条为新内容", removed, len(new_items))

    return new_items
