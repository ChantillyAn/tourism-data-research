"""RSS 源采集"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

import feedparser
import requests
from bs4 import BeautifulSoup

from src.config import RSS_FEEDS

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
_TIMEOUT = 15


@dataclass(frozen=True)
class FeedItem:
    """RSS 采集到的原始条目"""
    title: str
    url: str
    source: str
    published: str
    content_snippet: str


def fetch_feed(name: str, rss_url: str) -> list[FeedItem]:
    """拉取单个 RSS 源，返回条目列表"""
    try:
        feed = feedparser.parse(rss_url)
        if feed.bozo and not feed.entries:
            log.warning("RSS 解析异常 (%s): %s", name, feed.bozo_exception)
            return []

        items: list[FeedItem] = []
        for entry in feed.entries:
            snippet = _extract_snippet(entry)
            items.append(FeedItem(
                title=entry.get("title", "").strip(),
                url=entry.get("link", ""),
                source=name,
                published=entry.get("published", ""),
                content_snippet=snippet,
            ))
        log.info("RSS [%s] 获取 %d 条", name, len(items))
        return items

    except Exception as exc:
        log.error("RSS 拉取失败 (%s): %s", name, exc)
        return []


def fetch_all_feeds() -> list[FeedItem]:
    """拉取所有已配置的 RSS 源"""
    if not RSS_FEEDS:
        log.info("未配置 RSS 源，跳过 RSS 采集")
        return []

    all_items: list[FeedItem] = []
    for name, url in RSS_FEEDS.items():
        all_items.extend(fetch_feed(name, url))

    log.info("RSS 采集完成，共 %d 条", len(all_items))
    return all_items


def extract_article_content(url: str) -> str:
    """提取网页正文文本（用于补充 RSS 摘要不足时）"""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        # 尝试常见正文容器
        for selector in ("#js_content", "article", ".article-content", ".post-content", "main"):
            el = soup.select_one(selector)
            if el:
                return el.get_text(strip=True)[:2000]

        # 回退: 取 body 文本
        body = soup.find("body")
        return body.get_text(strip=True)[:2000] if body else ""

    except Exception as exc:
        log.warning("正文提取失败 (%s): %s", url, exc)
        return ""


def _extract_snippet(entry: dict) -> str:
    """从 RSS entry 中提取内容摘要"""
    # 优先用 summary，其次 content
    if hasattr(entry, "summary") and entry.summary:
        text = BeautifulSoup(entry.summary, "html.parser").get_text(strip=True)
        return text[:500]

    if hasattr(entry, "content") and entry.content:
        text = BeautifulSoup(entry.content[0].get("value", ""), "html.parser").get_text(strip=True)
        return text[:500]

    return ""
