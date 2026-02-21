# 文旅数据研究工具

输入一条查询，自动搜索公开数据源，提取网页内容，通过 LLM 分析生成包含文字、表格和图表的研究报告。

面向文旅、酒店、会展从业者和研究人员。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 LLM API Key（交互式引导）
python research.py setup

# 3. 运行研究查询
python research.py "四川省2024年旅游数据分析"
```

输出文件保存在 `data/reports/` 下，包含 Markdown 报告和图表。

## 支持的 LLM 提供商

所有兼容 OpenAI 格式的模型均可使用，仅需配置 API Key：

| 提供商 | 推荐场景 | 参考成本/次 |
|--------|---------|------------|
| **DeepSeek**（默认）| 通用，性价比高 | ~¥0.02-0.05 |
| Kimi（月之暗面）| 长文本分析 | ~¥0.05-0.1 |
| 智谱 GLM | 中文理解 | ~¥0.01-0.03 |
| MiniMax | 多模态 | ~¥0.02-0.05 |
| 自定义 | 兼容 OpenAI 格式的任意服务 | — |

## 命令

```bash
# 研究查询
python research.py "你的查询"
python research.py "查询" --output ./my-reports    # 指定输出目录
python research.py "查询" --no-charts              # 不生成图表
python research.py "查询" --model deepseek-chat     # 指定模型

# 配置
python research.py setup                            # 引导式配置

# 历史记录
python research.py history                          # 查看研究历史
python research.py show <session-id>                # 查看指定报告
```

## 工作流程

```
用户输入查询
  ↓
LLM 解析查询意图 → 生成 3-5 个搜索查询
  ↓
搜索引擎检索 → 去重 → 最多 15 个来源
  ↓
提取网页正文内容
  ↓
LLM 分析数据 → 结构化报告（章节、数据表、图表建议）
  ↓
渲染 Markdown 报告 + matplotlib 图表
  ↓
保存到 data/reports/{date}_{slug}/
```

## 输出结构

每次查询生成一个目录：

```
data/reports/2026-02-21_四川省2024年旅游数据分析/
├── report.md          # Markdown 研究报告
├── charts/            # PNG 图表
│   ├── chart_1.png
│   └── chart_2.png
└── data/              # 原始数据
    ├── analysis.json
    └── search_strategy.json
```

## 项目结构

```
├── research.py              # 研究工具入口
├── src/
│   ├── cli.py               # CLI 命令解析
│   ├── research_pipeline.py # 研究管线（串联全流程）
│   ├── llm_client.py        # LLM API 调用（兼容 OpenAI 格式）
│   ├── setup_wizard.py      # API Key 配置引导
│   ├── config.py            # 全局配置
│   ├── collectors/
│   │   ├── web_search.py    # 多引擎搜索（DuckDuckGo/博查/Tavily）
│   │   └── content_extractor.py # 网页内容提取
│   ├── analyzers/
│   │   ├── query_parser.py  # 查询 → 搜索策略
│   │   ├── data_analyzer.py # 数据 → 结构化报告
│   │   └── prompts/         # LLM 提示词模板
│   ├── generators/
│   │   ├── report.py        # Markdown 报告渲染
│   │   ├── charts.py        # matplotlib 图表
│   │   └── templates/       # Jinja2 模板
│   ├── db/
│   │   └── cache.py         # 研究缓存（SQLite）
│   └── utils/
│       ├── display.py       # 终端显示（rich）
│       └── json_extract.py  # LLM 输出 JSON 提取
├── data/                    # 运行时数据（不入 Git）
├── requirements.txt
├── .env.example
└── LICENSE
```

## 配置

配置存储在项目根目录 `.env` 文件中：

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

运行 `python research.py setup` 可交互式完成配置。

## 搜索引擎

| 引擎 | 特点 | API Key |
|------|------|---------|
| **DuckDuckGo**（默认）| 免费，零配置 | 不需要 |
| 博查（Bocha）| 中文搜索质量最好 | 需要 |
| Tavily | 免费 1000 次/月 | 需要 |

## 依赖

- Python 3.10+
- `requests` — HTTP 请求 + LLM API 调用
- `beautifulsoup4` — 网页解析
- `matplotlib` — 图表生成
- `rich` — 终端美化
- `jinja2` — 模板渲染
- `python-dotenv` — 环境变量
- `ddgs` — DuckDuckGo 搜索

## License

MIT
