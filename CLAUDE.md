# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Tourism Data Research Toolkit** — an open-source tool for China's cultural tourism, hotel, and exhibition sectors. Users input a natural language query (e.g., "四川省2024年旅游数据分析"), and the tool automatically searches, extracts, analyzes data, and generates a research report with text, tables, and charts.

The project also includes a legacy daily briefing generator (via `src/main.py`).

## CLI Commands

### Research Tool (primary)

```bash
pip install -r requirements.txt          # Install dependencies (one-time)

python research.py setup                 # Interactive LLM API key configuration
python research.py "查询内容"             # Run a research query
python research.py "查询" --output ./dir  # Custom output directory
python research.py "查询" --no-charts     # Skip chart generation
python research.py "查询" --model NAME    # Override LLM model
python research.py history               # List research sessions
python research.py show <session-id>     # View a specific report
```

### Legacy Daily Briefing

```bash
python src/main.py fetch                 # Pull RSS feeds, deduplicate, output new items JSON
python src/main.py save <file.json>      # Validate and insert classified items into SQLite
python src/main.py render                # Render today's briefing → data/output/daily/YYYY-MM-DD.md
python src/main.py history               # List recent briefings
```

## Architecture

### Research Pipeline: **Query → Parse → Search → Extract → Analyze → Render**

```
src/
├── cli.py                      # Research CLI (argparse dispatcher)
├── research_pipeline.py        # Full pipeline orchestration
├── setup_wizard.py             # Interactive API key setup
├── config.py                   # All configuration (paths, LLM providers, search params)
├── collectors/
│   ├── web_search.py           # DuckDuckGo search via duckduckgo-search
│   ├── content_extractor.py    # Web page content extraction (BeautifulSoup4)
│   └── rss.py                  # RSS feed collection (legacy)
├── analyzers/
│   ├── query_parser.py         # LLM: query → structured search strategy
│   ├── data_analyzer.py        # LLM: data → structured analysis
│   └── prompts/
│       ├── query_parse.txt     # System prompt for query parsing
│       └── analyze.txt         # System prompt for data analysis
├── generators/
│   ├── report.py               # Jinja2 Markdown report rendering
│   ├── charts.py               # matplotlib chart generation (Chinese fonts)
│   └── templates/
│       └── report.md.j2        # Report template
├── db/
│   ├── cache.py                # Research cache + session tracking (SQLite)
│   └── models.py               # Legacy briefing database
├── processors/                 # Legacy briefing processors
├── templates/daily.md.j2       # Legacy briefing template
└── utils/
    └── display.py              # rich terminal output
```

**Research data flow**: User query → `query_parser` generates search queries → `web_search` searches DuckDuckGo → `content_extractor` extracts page text → `data_analyzer` produces structured analysis → `report.py` renders Markdown → `charts.py` generates PNG charts → output saved to `data/reports/`.

**Key design choices**:
- All LLM calls go through `openai` SDK with configurable `base_url` (supports DeepSeek, Kimi, GLM, MiniMax)
- Search results cached in SQLite (`data/cache.db`, 24h TTL)
- Frozen dataclasses for data objects (immutable)
- Session tracking for research history
- Graceful degradation: if content extraction fails, falls back to search snippets

**LLM Configuration** (stored in `.env`):
- `LLM_PROVIDER`: deepseek, kimi, glm, minimax, or custom
- `LLM_API_KEY`: API key
- `LLM_BASE_URL`: Override base URL
- `LLM_MODEL`: Override model name

## Editorial Guidelines

- Report only facts and data that have already occurred — no predictions
- Every data point must cite its source
- Data items must include specific numbers with comparisons
- No sensationalist language ("震惊", "重磅", etc.)
- Tone: professional, concise, neutral
- LLM-generated analysis must include a "limitations" section

## Key Documentation

- `docs/PRD.md` — Product requirements, user personas, content strategy
- `docs/SPEC.md` — Technical spec, infrastructure plan
- `README.md` — User-facing documentation
