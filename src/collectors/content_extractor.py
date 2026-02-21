"""网页内容提取 — 从现有 rss.py 提取复用"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from src.config import CONTENT_EXTRACT_MAX_CHARS, CONTENT_EXTRACT_TIMEOUT

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


@dataclass(frozen=True)
class ExtractedContent:
    """提取的网页内容"""
    url: str
    title: str
    text: str
    success: bool


def extract_content(url: str) -> ExtractedContent:
    """提取网页正文文本"""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=CONTENT_EXTRACT_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        text = _extract_body(soup)

        return ExtractedContent(
            url=url,
            title=title,
            text=text[:CONTENT_EXTRACT_MAX_CHARS],
            success=bool(text),
        )

    except Exception as exc:
        log.warning("内容提取失败 (%s): %s", url, exc)
        return ExtractedContent(url=url, title="", text="", success=False)



def _extract_body(soup: BeautifulSoup) -> str:
    """从 HTML 中提取正文文本"""
    # 移除无关标签
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # 尝试常见正文容器
    for selector in (
        "#js_content",  # 微信公众号
        "article",
        ".article-content",
        ".post-content",
        ".entry-content",
        ".content",
        "main",
        "[role='main']",
    ):
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 100:
                return text

    # 回退: 取 body 文本
    body = soup.find("body")
    if body:
        return body.get_text(separator="\n", strip=True)

    return ""
