"""matplotlib 图表生成"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 非交互式后端
import matplotlib.pyplot as plt

log = logging.getLogger(__name__)

# ── 中文字体配置 ──────────────────────────────────────
_FONT_CANDIDATES = [
    "Microsoft YaHei",   # Windows
    "SimHei",            # Windows 备选
    "PingFang SC",       # macOS
    "Noto Sans CJK SC",  # Linux
    "WenQuanYi Micro Hei",  # Linux 备选
]

_font_initialized = False


def _setup_chinese_font() -> None:
    """配置 matplotlib 中文字体（首次生成图表时调用）"""
    global _font_initialized
    if _font_initialized:
        return
    _font_initialized = True

    from matplotlib.font_manager import fontManager

    available_fonts = {f.name for f in fontManager.ttflist}

    for font_name in _FONT_CANDIDATES:
        if font_name in available_fonts:
            plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            log.info("使用中文字体: %s", font_name)
            return

    log.warning("未找到中文字体，图表中文可能显示异常")
    plt.rcParams["axes.unicode_minus"] = False


# ── 颜色方案 ──────────────────────────────────────────
COLORS = [
    "#2563eb",  # 蓝
    "#dc2626",  # 红
    "#16a34a",  # 绿
    "#ca8a04",  # 黄
    "#9333ea",  # 紫
    "#0891b2",  # 青
    "#ea580c",  # 橙
    "#64748b",  # 灰
]


def generate_charts(charts_data: list[dict], output_dir: Path) -> list[Path]:
    """根据分析结果生成图表

    Args:
        charts_data: LLM 返回的 charts 数组
        output_dir: 图表输出目录

    Returns:
        生成的图表文件路径列表
    """
    _setup_chinese_font()
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    for i, chart in enumerate(charts_data, 1):
        chart_type = chart.get("type", "bar")
        title = chart.get("title", f"图表 {i}")
        data = chart.get("data", {})

        if not data.get("labels") or not data.get("datasets"):
            log.warning("图表 %d 数据不完整，跳过", i)
            continue

        try:
            path = output_dir / f"chart_{i}.png"

            if chart_type == "bar":
                _render_bar(data, title, path)
            elif chart_type == "line":
                _render_line(data, title, path)
            elif chart_type == "pie":
                _render_pie(data, title, path)
            else:
                log.warning("不支持的图表类型: %s，使用柱状图", chart_type)
                _render_bar(data, title, path)

            generated.append(path)
            log.info("图表已生成: %s", path)

        except Exception as exc:
            log.error("图表 %d 生成失败: %s", i, exc)

    return generated


def _align_data(labels: list, values: list) -> tuple[list, list]:
    """对齐 labels 和 values 的长度，防止 matplotlib 报错"""
    min_len = min(len(labels), len(values))
    return labels[:min_len], values[:min_len]


def _render_bar(data: dict, title: str, path: Path) -> None:
    """渲染柱状图"""
    labels = data["labels"]
    datasets = data["datasets"]

    fig, ax = plt.subplots(figsize=(10, 6))

    bar_width = 0.8 / max(len(datasets), 1)
    for j, ds in enumerate(datasets):
        values = ds.get("values", [])
        aligned_labels, aligned_values = _align_data(labels, values)
        if not aligned_labels:
            continue
        offset = (j - len(datasets) / 2 + 0.5) * bar_width
        positions = [x + offset for x in range(len(aligned_labels))]
        ax.bar(
            positions, aligned_values,
            width=bar_width,
            label=ds.get("label", ""),
            color=COLORS[j % len(COLORS)],
        )

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_title(title, fontsize=14, fontweight="bold")
    if len(datasets) > 1:
        ax.legend()
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    plt.close(fig)


def _render_line(data: dict, title: str, path: Path) -> None:
    """渲染折线图"""
    labels = data["labels"]
    datasets = data["datasets"]

    fig, ax = plt.subplots(figsize=(10, 6))

    for j, ds in enumerate(datasets):
        values = ds.get("values", [])
        aligned_labels, aligned_values = _align_data(labels, values)
        if not aligned_labels:
            continue
        ax.plot(
            aligned_labels, aligned_values,
            marker="o",
            label=ds.get("label", ""),
            color=COLORS[j % len(COLORS)],
            linewidth=2,
        )

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.xticks(rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    plt.close(fig)


def _render_pie(data: dict, title: str, path: Path) -> None:
    """渲染饼图"""
    labels = data["labels"]
    datasets = data["datasets"]
    values = datasets[0].get("values", []) if datasets else []

    aligned_labels, aligned_values = _align_data(labels, values)
    if not aligned_values or all(v == 0 for v in aligned_values):
        log.warning("饼图 '%s' 没有有效数据，跳过", title)
        return

    fig, ax = plt.subplots(figsize=(8, 8))

    colors = COLORS[:len(aligned_labels)]
    ax.pie(
        aligned_values,
        labels=aligned_labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.85,
    )
    ax.set_title(title, fontsize=14, fontweight="bold")

    fig.tight_layout()
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    plt.close(fig)
