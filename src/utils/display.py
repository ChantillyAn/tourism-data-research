"""终端显示工具 — 基于 rich"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table


class Display:
    """封装终端输出，提供统一的显示风格"""

    def __init__(self) -> None:
        self.console = Console()
        self._step_count = 0

    def step(self, message: str) -> None:
        """显示流程步骤"""
        self._step_count += 1
        self.console.print(f"\n[bold cyan][{self._step_count}][/bold cyan] {message}")

    def info(self, message: str) -> None:
        self.console.print(f"  [dim]{message}[/dim]")

    def detail(self, message: str) -> None:
        self.console.print(f"    [dim]{message}[/dim]")

    def success(self, message: str) -> None:
        self.console.print(f"[bold green]{message}[/bold green]")

    def warning(self, message: str) -> None:
        self.console.print(f"[yellow]{message}[/yellow]")

    def error(self, message: str) -> None:
        self.console.print(f"[bold red]{message}[/bold red]")

    def show_history(self, sessions: list[dict]) -> None:
        """显示研究历史表格"""
        table = Table(title="研究历史")
        table.add_column("会话 ID", style="cyan", no_wrap=True)
        table.add_column("查询", style="white")
        table.add_column("状态", style="green")
        table.add_column("来源数", justify="right")
        table.add_column("时间", style="dim")

        for s in sessions:
            status_style = {
                "completed": "[green]completed[/green]",
                "running": "[yellow]running[/yellow]",
                "failed": "[red]failed[/red]",
            }.get(s["status"], s["status"])

            table.add_row(
                s["id"],
                _truncate(s["query"], 40),
                status_style,
                str(s.get("sources_count") or "—"),
                s.get("created_at", "")[:16],
            )

        self.console.print(table)

    def show_session(self, session: dict) -> None:
        """显示单个会话详情"""
        self.console.print(f"\n[bold]会话 ID:[/bold] {session['id']}")
        self.console.print(f"[bold]查询:[/bold] {session['query']}")
        self.console.print(f"[bold]状态:[/bold] {session['status']}")
        self.console.print(f"[bold]来源数:[/bold] {session.get('sources_count', '—')}")
        self.console.print(f"[bold]创建时间:[/bold] {session.get('created_at', '')}")

        if session.get("completed_at"):
            self.console.print(f"[bold]完成时间:[/bold] {session['completed_at']}")

        if session.get("report_path"):
            self.console.print(f"[bold]报告路径:[/bold] {session['report_path']}")


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
