"""文旅数据简报 — CLI 主入口

用法:
    python src/main.py fetch              拉取 RSS 并去重，输出新条目 JSON
    python src/main.py save  <json_file>  保存已分类条目到数据库
    python src/main.py render [--date D]  从数据库渲染日报 Markdown
    python src/main.py history [--days N] 查看最近日报列表
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

# 确保 src/ 的父目录在 sys.path 中，支持从任意位置运行
_src_dir = Path(__file__).resolve().parent
_root_dir = _src_dir.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from src.collectors.rss import FeedItem, fetch_all_feeds
from src.config import DAILY_OUTPUT_DIR, DATA_DIR, VALID_CATEGORIES
from src.db.models import (
    get_connection,
    get_today_items,
    list_briefings,
    save_briefing,
    save_classified_items,
)
from src.processors.deduplicator import filter_new
from src.processors.formatter import render_daily

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


# ── 子命令 ────────────────────────────────────────────

def cmd_fetch(_args: argparse.Namespace) -> None:
    """拉取 RSS 源，去重后输出新条目 JSON"""
    conn = get_connection()
    try:
        raw_items = fetch_all_feeds()
        if not raw_items:
            log.info("RSS 未返回任何条目（可能未配置 RSS 源）")
            print(json.dumps([], ensure_ascii=False, indent=2))
            return

        new_items = filter_new(raw_items, conn)
        log.info("新条目: %d / %d", len(new_items), len(raw_items))

        output = [asdict(item) for item in new_items]
        print(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def cmd_save(args: argparse.Namespace) -> None:
    """保存已分类条目到数据库"""
    json_path = Path(args.json_file)
    if not json_path.exists():
        log.error("文件不存在: %s", json_path)
        sys.exit(1)

    items = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        log.error("JSON 文件应为数组格式")
        sys.exit(1)

    # 校验
    errors: list[str] = []
    for i, item in enumerate(items):
        if "title" not in item or "summary" not in item or "category" not in item:
            errors.append(f"条目 {i}: 缺少 title/summary/category")
        elif item["category"] not in VALID_CATEGORIES:
            errors.append(f"条目 {i}: category '{item['category']}' 无效，应为 {VALID_CATEGORIES}")

    if errors:
        for e in errors:
            log.error(e)
        sys.exit(1)

    conn = get_connection()
    try:
        count = save_classified_items(conn, items)
        log.info("已保存 %d 条分类条目", len(items))
    finally:
        conn.close()


def cmd_render(args: argparse.Namespace) -> None:
    """从数据库读取今日条目，渲染日报 Markdown"""
    target = _parse_date(args.date) if args.date else date.today()

    conn = get_connection()
    try:
        items = get_today_items(conn, target)
        log.info("日期 %s 共 %d 条分类条目", target.isoformat(), len(items))

        markdown = render_daily(items, target)

        # 保存到文件
        DAILY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = DAILY_OUTPUT_DIR / f"{target.isoformat()}.md"
        out_path.write_text(markdown, encoding="utf-8")
        log.info("日报已保存: %s", out_path)

        # 保存到数据库
        save_briefing(conn, target, markdown, len(items))

        # 同时输出到 stdout
        print(markdown)
    finally:
        conn.close()


def cmd_history(args: argparse.Namespace) -> None:
    """查看最近日报列表"""
    conn = get_connection()
    try:
        briefings = list_briefings(conn, days=args.days)
        if not briefings:
            print("暂无日报记录")
            return

        print(f"最近 {args.days} 天日报:")
        print("-" * 50)
        for b in briefings:
            status = "✓ 已发布" if b["published"] else "  草稿"
            print(f"  {b['date']}  {status}  ({b['items_count'] or 0} 条)")
    finally:
        conn.close()


# ── 工具 ──────────────────────────────────────────────

def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        log.error("日期格式错误: %s（应为 YYYY-MM-DD）", s)
        sys.exit(1)


# ── CLI ───────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="travel-briefing",
        description="文旅数据简报 — Phase 0 CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("fetch", help="拉取 RSS 并去重，输出新条目 JSON")

    p_save = sub.add_parser("save", help="保存已分类条目到数据库")
    p_save.add_argument("json_file", help="已分类条目 JSON 文件路径")

    p_render = sub.add_parser("render", help="渲染日报 Markdown")
    p_render.add_argument("--date", help="指定日期 (YYYY-MM-DD)，默认今天")

    p_hist = sub.add_parser("history", help="查看最近日报列表")
    p_hist.add_argument("--days", type=int, default=7, help="查看天数 (默认 7)")

    args = parser.parse_args()

    # 确保 data 目录存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    commands = {
        "fetch": cmd_fetch,
        "save": cmd_save,
        "render": cmd_render,
        "history": cmd_history,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
