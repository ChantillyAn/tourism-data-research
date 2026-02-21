"""文旅数据简报 + 研究工具 — 全局配置"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── 路径 ──────────────────────────────────────────────
# 项目根目录：src/ 的父目录
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "briefing.db"
OUTPUT_DIR = DATA_DIR / "output"
DAILY_OUTPUT_DIR = OUTPUT_DIR / "daily"
WEEKLY_OUTPUT_DIR = OUTPUT_DIR / "weekly"
MONTHLY_OUTPUT_DIR = OUTPUT_DIR / "monthly"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# ── 研究工具路径 ──────────────────────────────────────
CACHE_DB_PATH = DATA_DIR / "cache.db"
REPORTS_DIR = DATA_DIR / "reports"
RESEARCH_TEMPLATES_DIR = Path(__file__).resolve().parent / "generators" / "templates"

# ── LLM 配置 ─────────────────────────────────────────
LLM_PROVIDERS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "name": "DeepSeek",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "name": "Kimi（月之暗面）",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "name": "智谱 GLM",
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "abab6.5s-chat",
        "name": "MiniMax",
    },
}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")


def get_llm_config() -> dict[str, str]:
    """返回当前 LLM 配置（base_url, api_key, model）"""
    provider_info = LLM_PROVIDERS.get(LLM_PROVIDER, {})
    return {
        "api_key": LLM_API_KEY,
        "base_url": LLM_BASE_URL or provider_info.get("base_url", ""),
        "model": LLM_MODEL or provider_info.get("default_model", ""),
    }


# ── 搜索配置 ─────────────────────────────────────────
SEARCH_PROVIDERS: dict[str, dict[str, str]] = {
    "bocha": {
        "name": "Bocha（博查）",
        "endpoint": "https://api.bochaai.com/v1/web-search",
        "description": "国产搜索 API，中文质量最好，~¥0.02/次",
    },
    "tavily": {
        "name": "Tavily",
        "endpoint": "https://api.tavily.com/search",
        "description": "AI 专用搜索，免费 1000 次/月",
    },
    "ddgs": {
        "name": "DuckDuckGo（免费）",
        "endpoint": "",
        "description": "免费，无需 API key，中文质量较差",
    },
}

SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "ddgs")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "")
SEARCH_MAX_RESULTS: int = 10
CONTENT_EXTRACT_MAX_CHARS: int = 3000
CONTENT_EXTRACT_TIMEOUT: int = 15

# ── 缓存配置 ─────────────────────────────────────────
CACHE_TTL_HOURS: int = 24

# ── RSS 源 ────────────────────────────────────────────
# Phase 0: 经验证可用的公开 RSS 源（2026-02-20 验证）
# 格式: "来源名称": "RSS 地址"
# 注意: rsshub.app 在大陆可能不通，可替换为 rsshub.rssforever.com
RSSHUB_INSTANCE = "https://rsshub.rssforever.com"

RSS_FEEDS: dict[str, str] = {
    # ── 文旅行业媒体 ──
    "品橙旅游": "https://www.pinchain.com/feed",
    "界面新闻·文旅": f"{RSSHUB_INSTANCE}/jiemian/lists/105",

    # ── 政府政策与统计数据 ──
    "国务院政策·部门文件": f"{RSSHUB_INSTANCE}/gov/zhengce/zhengceku/bmwj",
    "国家统计局·数据发布": f"{RSSHUB_INSTANCE}/gov/stats/sj/zxfb",

    # ── 综合新闻（含文旅报道）──
    "财联社·快讯": f"{RSSHUB_INSTANCE}/cls/telegraph",
    "中国新闻网·即时": "https://www.chinanews.com.cn/rss/scroll-news.xml",

    # ── 以下源无公开 RSS，依赖 WebSearch 补充 ──
    # 环球旅讯 (traveldaily.cn)    — 无 RSS
    # 迈点网 (meadin.com)          — 无 RSS
    # 执惠 (tripvivid.com)         — 无 RSS
    # 中国旅游报 (ctnews.com.cn)   — 无 RSS
    # 文旅部 (mct.gov.cn)          — 无 RSSHub 路由
}

# ── 去重 ──────────────────────────────────────────────
# 与最近 N 天内的已处理条目比较，避免重复报道
DEDUP_WINDOW_DAYS: int = 3

# ── 日报 ──────────────────────────────────────────────
# 每个板块最多展示的条目数
DAILY_MAX_POLICIES: int = 3
DAILY_MAX_DATA_POINTS: int = 3
DAILY_MAX_HOT_TOPICS: int = 2

# ── 分类 ──────────────────────────────────────────────
VALID_CATEGORIES = frozenset({"政策动态", "数据快报", "行业热点"})
