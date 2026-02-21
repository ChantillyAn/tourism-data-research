# Phase 0 实施方案：本地 Claude Code 驱动

> 版本：v0.1
> 日期：2026-02-20
> 状态：草稿
> 前置文档：[PRD.md](../PRD.md)、[SPEC.md](../SPEC.md)

---

## 1. 方案定位

Phase 0 是产品的冷启动阶段。用最低成本验证内容质量和用户需求，再决定是否投入 SPEC v0.2 描述的全自动化基础设施。

| 维度 | Phase 0（本文档） | Phase 1（SPEC v0.2） |
|---|---|---|
| 运行环境 | 本地电脑 + Claude Code | 腾讯云服务器 + Docker + cron |
| LLM | Claude Code 自身（Opus 4.6） | DeepSeek V3（日报）+ Claude API（周报/月报） |
| 数据采集 | WebSearch + 手动浏览 + 部分 RSS | changedetection.io + 今天看啥 VIP + RSSHub |
| 发布 | wechat-article-publisher-skill | 微信公众号 API + Hugo 网站 |
| 自动化程度 | 手动触发，每天 10-15 分钟 | 全自动，每天 5 分钟审核 |
| 额外成本 | ¥0（已有 Claude Code 订阅） | ~¥125/月 |
| 网站 | 无 | Hugo + Vercel |
| 升级条件 | 日报稳定运行 1-2 个月 + 100+ 关注者 | — |

---

## 2. Phase 0 不变的内容（继承自 PRD v0.3）

以下内容与 PRD v0.3 完全一致，不因实现方式改变而改变：

- 内容产品定义（日报/周报/月报的模板、篇幅、价格）→ PRD 第 4 章
- 编辑准则与品牌调性 → PRD 第 4.5 节
- 内容日历 → PRD 第 4.6 节
- 质量标准（来源标注、不凑数、不预测） → PRD 第 4.1/4.2/4.3 节
- 目标用户画像 → PRD 第 2 章
- 异常情况处理 → PRD 第 4.7 节

---

## 3. 技术栈

### 3.1 核心工具

| 工具 | 用途 | 来源 |
|---|---|---|
| **Claude Code** | 运行环境 + LLM 分析引擎 | 已有订阅 |
| **wechat-article-publisher-skill** | Markdown → 公众号草稿箱 | [GitHub](https://github.com/iamzifei/wechat-article-publisher-skill)，已安装 |
| **feedparser** | RSS 源解析 | Python 标准库级别 |
| **BeautifulSoup4** | HTML 正文提取 | Python 库 |
| **SQLite** | 已报道事件去重 + 数据归档 | Python 内置 |
| **Jinja2** | 日报模板渲染 | Python 库 |

### 3.2 Python 依赖

```
feedparser
beautifulsoup4
requests
jinja2
python-dotenv
```

### 3.3 环境变量

```bash
# .env
WECHAT_API_KEY=          # wx.limyai.com 获取
```

---

## 4. 信息源（Phase 0 简化版）

Phase 0 的信息采集分为两个层级：

### 4.1 自动采集（有公开 RSS 的来源）

以下行业媒体和平台有公开 RSS 源，可以用 feedparser 自动拉取：

| 来源 | RSS 地址 | 说明 |
|---|---|---|
| 环球旅讯 | 待确认 | 行业深度报道 |
| 品橙旅游 | 待确认 | 产业链资讯 |
| 界面新闻·旅游 | 待确认 | 财经视角 |
| 文旅部官网 | 待确认（RSSHub 路由） | 国家级政策 |

> 注：具体 RSS 地址需要在实施时逐个验证。部分来源可能需要通过 RSSHub 公共实例转换。

### 4.2 搜索采集（Claude Code WebSearch）

以下信息通过 Claude Code 的 WebSearch 功能搜索获取：

| 搜索策略 | 搜索词示例 | 目标信息 |
|---|---|---|
| 省级政策 | "文旅厅 通知 2026" "文化旅游 政策 今天" | 各省新发布的政策文件 |
| 行业数据 | "旅游 数据 同比" "游客量 2026" | OTA 和官方发布的数据 |
| 行业事件 | "景区 新闻 今日" "酒店 行业 动态" | 热点事件和企业动态 |
| 节假日数据 | "清明 旅游 数据" （假期后） | 假期专项数据 |

### 4.3 手动浏览（运营者每天 5-10 分钟）

重点关注以下公众号（Phase 0 优先级最高的 10 个）：

| 优先级 | 公众号 | 原因 |
|---|---|---|
| P0 | 文旅之声 | 文旅部官方，国家级政策第一来源 |
| P0 | 中国旅游研究院 | 权威统计数据 |
| P0 | 环球旅讯 | 行业深度分析 |
| P0 | 品橙旅游 | 产业链全覆盖 |
| P0 | 携程旅行 | OTA 数据报告 |
| P1 | 迈点网 | 酒店数据 |
| P1 | 执惠 | 文旅营销 |
| P1 | 景鉴智库 | 景区研究 |
| P1 | 中国旅游报 | 官方媒体 |
| P1 | 前瞻产业研究院 | 市场数据 |

---

## 5. 每日运营流程

### 5.1 日报生产 SOP

```
每天早上（含周末和节假日）：

07:00  打开 Claude Code，执行日报生成脚本
       ├── Python 脚本自动拉取可用 RSS 源
       ├── Claude Code WebSearch 搜索当天文旅新闻
       ├── 读取 SQLite 已报道事件库（去重）
       ├── Claude Code 分析、分类、生成摘要
       ├── Jinja2 模板渲染日报 Markdown
       └── 保存日报文件 + 更新事件库

07:15  运营者审核日报内容（3 分钟）
       ├── 检查内容准确性和来源标注
       ├── 必要时微调措辞
       └── 确认可以发布

07:20  使用 wechat-article-publisher-skill 发布到公众号草稿箱
       └── 设置定时发送（08:00）

08:00  公众号自动推送
```

### 5.2 周报生产 SOP（每周一期）

```
周日晚：
18:00  打开 Claude Code
       ├── 读取本周所有已处理数据（SQLite）
       ├── Claude Code 生成周报初稿
       └── 保存为 Markdown 文件

周日晚 - 周一早：
       运营者编辑周报初稿（1-2 小时）
       ├── 校验数据和来源
       ├── 补充原创分析
       ├── 设置付费分割点
       └── 确认可以发布

周一 07:30：
       使用 wechat-article-publisher-skill 发布
       └── 设置定时发送（08:00）
```

### 5.3 月报生产 SOP（每月一期）

```
每月最后一天：
       Claude Code 聚合当月数据
       ├── 读取当月所有 processed_items
       ├── 生成月度统计和大纲
       └── 保存数据包

次月第 1-5 天：
       运营者基于数据包撰写月报（分 5 天完成）
       └── 使用 wechat-article-publisher-skill 发布
```

---

## 6. 项目目录结构

```
travel-data-briefing/
├── docs/                              # 项目文档（已有）
│   ├── PRD.md
│   ├── SPEC.md
│   ├── competitive-analysis.md
│   └── plans/
│       ├── 2026-02-19-design-decisions.md
│       └── phase0-implementation.md   # 本文档
│
├── src/                               # Python 源码
│   ├── collectors/
│   │   ├── __init__.py
│   │   └── rss.py                     # RSS 源采集（feedparser）
│   │
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── deduplicator.py            # 去重（SQLite）
│   │   └── formatter.py               # 日报 Jinja2 模板渲染
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── models.py                  # SQLite 初始化和查询
│   │
│   ├── prompts/
│   │   └── classify.txt               # 分类 prompt（Claude Code 使用）
│   │
│   ├── templates/
│   │   └── daily.md.j2                # 日报 Jinja2 模板
│   │
│   ├── config.py                      # RSS 源列表、配置
│   └── main.py                        # 主入口
│
├── data/                              # 运行时数据（不入 Git）
│   ├── briefing.db                    # SQLite 数据库
│   ├── output/                        # 生成的日报/周报/月报 Markdown
│   │   ├── daily/
│   │   ├── weekly/
│   │   └── monthly/
│   └── logs/
│
├── requirements.txt
├── .env                               # 环境变量（不入 Git）
├── .env.example
└── .gitignore
```

与 SPEC v0.2 对比，Phase 0 **去掉了**：
- `publishers/` 目录（使用 wechat-article-publisher-skill 替代）
- `memory/` 目录（简化为 db/models.py 中的去重逻辑）
- `site/` 目录（Phase 0 无网站）
- `docker-compose.yml`（Phase 0 不需要 Docker）
- `alert.py`（Phase 0 无告警系统）

---

## 7. 数据库（简化版）

Phase 0 只保留核心表：

```sql
-- 已处理的信息条目
CREATE TABLE processed_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    category TEXT NOT NULL,        -- 政策动态 | 数据快报 | 行业热点
    province TEXT,
    key_numbers TEXT,
    source TEXT NOT NULL,
    source_url TEXT,
    relevance_score INTEGER,
    processed_date DATE NOT NULL,
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- 日报归档
CREATE TABLE daily_briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,
    content_markdown TEXT NOT NULL,
    items_count INTEGER,
    published BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- 数据库版本
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT (datetime('now')),
    description TEXT
);
INSERT INTO schema_version (version, description)
VALUES (1, 'Phase 0 初始 schema');
```

与 SPEC v0.2 对比，Phase 0 **去掉了**：
- `raw_items` 表（Phase 0 不单独存储原始数据）
- `reported_events` 表（去重逻辑合并到 processed_items 查询中）
- `topic_heat` 表（Phase 1 再加）
- `source_quality` 表（Phase 1 再加）
- `province_activity` 表（Phase 1 再加）
- `policy_archive` 表（Phase 1 再加）
- `data_indicators` 表（Phase 1 再加）
- `report_drafts` 表（Phase 0 用文件管理草稿）

---

## 8. 日报生成主流程（伪代码）

```python
# src/main.py

def generate_daily():
    """Phase 0 日报生成主流程 — 由 Claude Code 触发"""

    # 1. 拉取 RSS 源
    rss_items = collectors.rss.fetch_all()

    # 2. 去重（对比最近 3 天的 processed_items）
    new_items = processors.deduplicator.filter_new(rss_items)

    # 3. 输出新条目供 Claude Code 分析
    #    Claude Code 在对话中完成分类和摘要
    #    （不调用外部 LLM API，用 Claude Code 自身能力）
    print_items_for_review(new_items)

    # 4. Claude Code 分析完成后，将结果写入数据库
    #    （这一步在 Claude Code 对话中交互完成）

    # 5. 渲染日报
    briefing = processors.formatter.render_daily(classified_items)

    # 6. 保存
    save_to_file(briefing, f"data/output/daily/{today()}.md")
    db.save_briefing(today(), briefing)

    # 7. 使用 wechat-article-publisher-skill 发布
    #    （在 Claude Code 中调用 skill）
```

**关键设计决策**：步骤 3 不调用外部 LLM API。Claude Code 自身就是 Opus 4.6，在对话中直接完成分析。这省去了 API 调用的代码和费用，但需要运营者在 Claude Code 对话中交互操作。

---

## 9. 从 Phase 0 升级到 Phase 1 的路径

当以下条件**同时满足**时，考虑升级到 SPEC v0.2 方案：

| 条件 | 标准 |
|---|---|
| 日报已稳定运行 | 连续 30 天无中断 |
| 内容质量验证 | 有用户反馈"有用" |
| 关注者积累 | 100+ 关注者 |
| 运营者确认可持续 | 每天 10-15 分钟的投入可以接受 |

升级步骤：

1. 购买腾讯云服务器
2. 部署 changedetection.io + RSSHub（SPEC 第 2-3 章）
3. 注册 今天看啥 VIP + 配置 RSS 源
4. 将 Phase 0 的 Python 脚本迁移到服务器（加 cron 定时）
5. 用 DeepSeek API 替代 Claude Code 自身做日报分类（降低成本）
6. 部署 Hugo 网站（SPEC 第 6.1 章）
7. 迁移 SQLite 数据（直接复制文件）

Phase 0 的代码和数据结构已为升级预留：
- `processed_items` 表结构与 SPEC v0.2 一致
- `daily_briefings` 表结构与 SPEC v0.2 一致
- Jinja2 模板可直接复用
- RSS 采集代码可直接复用

---

## 10. 待办事项

| 序号 | 事项 | 优先级 |
|---|---|---|
| 1 | 注册 wx.limyai.com，获取 WECHAT_API_KEY | P0 |
| 2 | 注册微信公众号（订阅号） | P0 |
| 3 | 验证行业媒体的公开 RSS 源可用性 | P0 |
| 4 | 编写 Python 采集和格式化脚本（~200 行） | P0 |
| 5 | 初始化 SQLite 数据库 | P0 |
| 6 | 试运行 3 天日报（不发布，只验证流程） | P0 |
| 7 | 正式发布第 1 期日报 | P0 |
