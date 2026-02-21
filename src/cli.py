"""研究工具 CLI — 命令解析与调度"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.config import REPORTS_DIR

logging.basicConfig(level=logging.WARNING, format="%(message)s")


def main() -> None:
    # 手动检查第一个参数决定走子命令还是查询
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        _print_help()
        return

    first_arg = sys.argv[1]

    if first_arg == "setup":
        from src.setup_wizard import run_setup
        run_setup()
    elif first_arg == "history":
        _cmd_history()
    elif first_arg == "show":
        if len(sys.argv) < 3:
            print("用法: python research.py show <session-id>")
            sys.exit(1)
        _cmd_show(sys.argv[2])
    elif first_arg.startswith("-"):
        # --output 等参数但没有查询
        _print_help()
    else:
        # 第一个参数就是查询字符串
        _cmd_research(sys.argv[1:])


def _print_help() -> None:
    print("""文旅数据研究工具 — 输入查询，自动搜索、分析、生成研究报告

用法:
  python research.py "查询内容"                 运行研究查询
  python research.py "查询" --output ./dir      指定输出目录
  python research.py "查询" --no-charts         不生成图表
  python research.py "查询" --model MODEL       指定 LLM 模型
  python research.py setup                      引导式 API key 配置
  python research.py history                    查看研究历史
  python research.py show <session-id>          查看指定研究报告""")


def _cmd_research(argv: list[str]) -> None:
    """执行研究查询"""
    parser = argparse.ArgumentParser(prog="research", add_help=False)
    parser.add_argument("query", help="研究查询")
    parser.add_argument("--output", type=str, default=None, help="报告输出目录")
    parser.add_argument("--no-charts", action="store_true", help="不生成图表")
    parser.add_argument("--model", type=str, default=None, help="指定 LLM 模型")
    args = parser.parse_args(argv)

    from src.setup_wizard import ensure_configured

    if not ensure_configured():
        return

    from src.utils.display import Display

    display = Display()

    try:
        from src.research_pipeline import run_research

        run_research(
            query=args.query,
            output_dir=args.output,
            no_charts=args.no_charts,
            model_override=args.model,
            display=display,
        )
    except KeyboardInterrupt:
        display.warning("\n用户中断")
        sys.exit(130)
    except Exception as exc:
        display.error(f"研究失败: {exc}")
        sys.exit(1)


def _cmd_history() -> None:
    """显示研究历史"""
    from src.db.cache import get_cache_connection, list_sessions
    from src.utils.display import Display

    display = Display()
    conn = get_cache_connection()
    sessions = list_sessions(conn, limit=20)
    conn.close()

    if not sessions:
        display.info("暂无研究记录")
        return

    display.show_history(sessions)


def _cmd_show(session_id: str) -> None:
    """查看指定研究报告"""
    from src.db.cache import get_cache_connection, get_session
    from src.utils.display import Display

    display = Display()
    conn = get_cache_connection()
    session = get_session(conn, session_id)
    conn.close()

    if not session:
        display.error(f"未找到会话: {session_id}")
        sys.exit(1)

    if not session.get("output_dir"):
        display.warning("该会话尚未生成报告")
        display.show_session(session)
        return

    # 查找报告文件
    stored = session["output_dir"]
    report_dir = Path(stored) if Path(stored).is_absolute() else REPORTS_DIR / stored
    report_file = report_dir / "report.md"
    if report_file.exists():
        display.info(f"报告路径: {report_file}")
        print(report_file.read_text(encoding="utf-8"))
    else:
        display.warning("报告文件不存在，显示会话摘要：")
        display.show_session(session)
