"""研究管线 — 串联搜索、分析、报告生成的完整流程"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from src.analyzers.data_analyzer import analyze_data
from src.analyzers.query_parser import parse_query
from src.collectors.content_extractor import extract_content
from src.collectors.web_search import search_multiple
from src.config import REPORTS_DIR
from src.db.cache import (
    create_session,
    get_cache_connection,
    get_cached_search,
    save_search_cache,
    update_session,
)
from src.generators.charts import generate_charts
from src.generators.report import render_report
from src.utils.display import Display

log = logging.getLogger(__name__)


def run_research(
    query: str,
    output_dir: str | None = None,
    no_charts: bool = False,
    model_override: str | None = None,
    display: Display | None = None,
) -> Path:
    """执行完整研究流程

    Returns:
        报告文件路径
    """
    if display is None:
        display = Display()

    conn = get_cache_connection()
    session_id = create_session(conn, query)

    display.step("解析查询...")

    # 1. 解析查询 → 搜索策略
    strategy = parse_query(query, model_override=model_override)
    search_queries = strategy.get("search_queries", [query])
    display.info(f"生成 {len(search_queries)} 个搜索查询")
    for sq in search_queries:
        display.detail(f"  - {sq}")

    update_session(conn, session_id, search_queries=search_queries)

    # 2. 搜索
    display.step("搜索数据源...")

    all_search_results = []
    for sq in search_queries:
        cached = get_cached_search(conn, sq)
        if cached is not None:
            display.detail(f"  [缓存] {sq}: {len(cached)} 条结果")
            all_search_results.extend(cached)
        else:
            results = search_multiple([sq], max_results_per_query=8)
            results_dicts = [asdict(r) for r in results]
            save_search_cache(conn, sq, results_dicts)
            display.detail(f"  [搜索] {sq}: {len(results_dicts)} 条结果")
            all_search_results.extend(results_dicts)

    # 去重
    seen_urls: set[str] = set()
    unique_results: list[dict] = []
    for r in all_search_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    display.info(f"共 {len(unique_results)} 个不重复来源")

    if not unique_results:
        display.warning("未找到搜索结果")
        update_session(conn, session_id, status="failed")
        conn.close()
        raise RuntimeError("搜索未返回任何结果，请尝试调整查询")

    # 3. 提取网页内容
    display.step("提取网页内容...")

    urls = [r["url"] for r in unique_results[:15]]  # 最多提取 15 个
    contents: list[dict] = []
    for url in urls:
        extracted = extract_content(url)
        if extracted.success:
            contents.append({
                "url": extracted.url,
                "title": extracted.title,
                "text": extracted.text,
            })

    display.info(f"成功提取 {len(contents)}/{len(urls)} 个页面")

    update_session(conn, session_id, sources_count=len(contents))

    # 如果提取结果不足，使用搜索摘要作为补充
    if len(contents) < 3:
        for r in unique_results:
            if r["url"] not in {c["url"] for c in contents}:
                contents.append({
                    "url": r["url"],
                    "title": r.get("title", ""),
                    "text": r.get("snippet", ""),
                })

    # 4. LLM 分析
    display.step("分析数据...")

    analysis = analyze_data(
        query=query,
        search_strategy=strategy,
        contents=contents,
        model_override=model_override,
    )

    display.info(f"分析完成: {len(analysis.get('sections', []))} 个章节")

    # 5. 生成报告
    display.step("生成报告...")

    report_output_dir = Path(output_dir) if output_dir else None
    report_path = render_report(analysis, query, output_dir=report_output_dir)
    report_dir = report_path.parent

    # 6. 生成图表
    charts_data = analysis.get("charts", [])
    if charts_data and not no_charts:
        display.step(f"生成 {len(charts_data)} 个图表...")
        charts_dir = report_dir / "charts"
        chart_paths = generate_charts(charts_data, charts_dir)
        display.info(f"生成 {len(chart_paths)} 个图表")

    # 7. 保存原始数据
    data_dir = report_dir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (data_dir / "search_strategy.json").write_text(
        json.dumps(strategy, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 8. 更新会话
    if REPORTS_DIR in report_dir.parents or report_dir == REPORTS_DIR:
        stored_dir = str(report_dir.relative_to(REPORTS_DIR))
    else:
        stored_dir = str(report_dir.resolve())
    update_session(
        conn,
        session_id,
        status="completed",
        output_dir=stored_dir,
        report_path=str(report_path),
    )
    conn.close()

    # 9. 输出结果
    display.success(f"\n报告已生成: {report_path}")
    display.info(f"会话 ID: {session_id}")

    return report_path
