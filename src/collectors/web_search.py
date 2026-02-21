"""多引擎网页搜索 — 支持 Bocha、Tavily、DuckDuckGo"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence
from urllib.parse import urlparse

import requests

from src.config import SEARCH_API_KEY, SEARCH_MAX_RESULTS, SEARCH_PROVIDER

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """搜索结果条目"""
    title: str
    url: str
    snippet: str
    source: str = ""


# ── 搜索调度 ──────────────────────────────────────────

def search(query: str, max_results: int = SEARCH_MAX_RESULTS) -> list[SearchResult]:
    """根据配置的 provider 执行搜索"""
    provider = SEARCH_PROVIDER.lower()

    if provider == "bocha":
        return _search_bocha(query, max_results)
    elif provider == "tavily":
        return _search_tavily(query, max_results)
    else:
        return _search_ddgs(query, max_results)


def search_multiple(queries: Sequence[str], max_results_per_query: int = SEARCH_MAX_RESULTS) -> list[SearchResult]:
    """执行多个搜索查询，合并并去重结果"""
    seen_urls: set[str] = set()
    all_results: list[SearchResult] = []

    for query in queries:
        results = search(query, max_results=max_results_per_query)
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                all_results.append(r)

    log.info("多查询搜索完成，共 %d 条去重结果", len(all_results))
    return all_results


# ── Bocha（博查）──────────────────────────────────────

def _search_bocha(query: str, max_results: int) -> list[SearchResult]:
    """通过博查 API 搜索"""
    try:
        resp = requests.post(
            "https://api.bochaai.com/v1/web-search",
            headers={
                "Authorization": f"Bearer {SEARCH_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "count": max_results,
                "summary": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("webPages", {}).get("value", []):
            results.append(SearchResult(
                title=item.get("name", ""),
                url=item.get("url", ""),
                snippet=item.get("summary") or item.get("snippet", ""),
                source=item.get("siteName", "") or _extract_domain(item.get("url", "")),
            ))

        log.info("Bocha 搜索 [%s] 获取 %d 条结果", query, len(results))
        return results

    except Exception as exc:
        log.error("Bocha 搜索失败 [%s]: %s", query, exc)
        return []


# ── Tavily ────────────────────────────────────────────

def _search_tavily(query: str, max_results: int) -> list[SearchResult]:
    """通过 Tavily API 搜索"""
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {SEARCH_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "api_key": SEARCH_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source=_extract_domain(item.get("url", "")),
            ))

        log.info("Tavily 搜索 [%s] 获取 %d 条结果", query, len(results))
        return results

    except Exception as exc:
        log.error("Tavily 搜索失败 [%s]: %s", query, exc)
        return []


# ── DuckDuckGo（通过 ddgs 包）────────────────────────

def _search_ddgs(query: str, max_results: int) -> list[SearchResult]:
    """通过 DuckDuckGo 搜索（免费，无需 API key）"""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            log.error("未安装搜索包，请运行: pip install ddgs")
            return []

    try:
        # ddgs 内部使用 httpx，在某些环境下 NO_PROXY 中的 IPv6 地址（::1）
        # 会导致 httpx URL 解析失败。临时清除以绕过。
        import os
        saved_no_proxy = os.environ.pop("NO_PROXY", None)
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(
                    query,
                    region="cn-zh",
                    max_results=max_results,
                ))
        finally:
            if saved_no_proxy is not None:
                os.environ["NO_PROXY"] = saved_no_proxy

        results = []
        for r in raw_results:
            results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
                source=_extract_domain(r.get("href", "")),
            ))

        log.info("DuckDuckGo 搜索 [%s] 获取 %d 条结果", query, len(results))
        return results

    except Exception as exc:
        log.error("DuckDuckGo 搜索失败 [%s]: %s", query, exc)
        return []


# ── 工具 ──────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    """从 URL 提取域名"""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""
