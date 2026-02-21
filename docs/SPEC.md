# 技术规格文档（SPEC）：文旅数据简报

> 版本：v0.2
> 日期：2026-02-20
> 状态：草稿，待评审
> 前置文档：[PRD.md](./PRD.md)
> 变更：技术栈从 n8n + DeepSeek + Coze 全面迁移至 Python脚本 + LLM API（Claude Code开发）

---

## 1. 系统架构总览

```
┌─────────────────────────────────────────────────────────┐
│                     数据采集层                            │
│                                                          │
│  changedetection.io       今天看啥 VIP + RSS   RSSHub   │
│  (31省文旅厅+文旅部)      (49个公众号)         (行业媒体) │
│         │                      │                  │      │
│         └──────────┬───────────┘──────────────────┘      │
│                    ↓                                      │
│          webhook / RSS / API                              │
└────────────────────┬──────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│              处理层：Python 自动化脚本                     │
│                                                          │
│  Cron/Systemd Timer (每天 06:30 触发)                     │
│       ↓                                                  │
│  collectors/ → 数据拉取（RSS + API + 手动输入）           │
│       ↓                                                  │
│  processors/deduplicator → 去重（对比SQLite已处理记录）    │
│       ↓                                                  │
│  processors/classifier → AI分类+摘要（LLM API）          │
│       ↓                                                  │
│  processors/formatter → 日报Markdown渲染（Jinja2模板）    │
│       ↓                                                  │
│  publishers/ → 发布到公众号 + 网站 + 数据库归档            │
└────────────────────┬──────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│                      发布层                               │
│                                                          │
│  微信公众号           静态网站            数据存储         │
│  (订阅号推送)         (Hugo/Vercel)      (SQLite)        │
└─────────────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│                     记忆层                                │
│                                                          │
│  已报道事件库    话题热度追踪    来源质量评分    省份活跃度 │
│  (events)       (topics)       (sources)      (provinces)│
└─────────────────────────────────────────────────────────┘
```

---

## 2. 基础设施

### 2.1 服务器

| 项目 | 规格 |
|------|------|
| 云服务商 | 腾讯云轻量应用服务器 |
| 配置 | 2核 CPU / 4GB 内存 / 60GB SSD |
| 操作系统 | Ubuntu 22.04 LTS |
| 月费 | ~80元 |
| 用途 | 运行 Python脚本 + changedetection.io + RSSHub |

### 2.2 容器化部署

changedetection.io 和 RSSHub 使用 Docker Compose 编排。Python 脚本直接运行在宿主机上（通过 venv 隔离），由 cron 或 systemd timer 调度。

```yaml
# docker-compose.yml
services:
  changedetection:
    image: ghcr.io/dgtlmoon/changedetection.io:latest
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./data/changedetection:/datastore
    environment:
      - PLAYWRIGHT_DRIVER_URL=ws://playwright:3000

  playwright:
    image: browserless/chrome:latest
    restart: unless-stopped

  rsshub:
    image: diygod/rsshub:latest
    restart: unless-stopped
    ports:
      - "1200:1200"
    environment:
      - NODE_ENV=production
      - CACHE_TYPE=memory
```

### 2.3 Python 运行环境

```bash
# Python 环境
python3.11+
pip install -r requirements.txt

# 核心依赖
feedparser          # RSS解析
requests            # HTTP请求
httpx               # 异步HTTP（可选）
jinja2              # 模板渲染
anthropic           # Claude API
openai              # DeepSeek API（兼容OpenAI格式）
beautifulsoup4      # HTML解析
schedule            # 任务调度（备选方案，主要用cron）
python-dotenv       # 环境变量管理
Pillow              # 信息卡片图生成（可选）
matplotlib          # 月报数据图表生成
```

### 2.4 域名与DNS

| 项目 | 说明 |
|------|------|
| 域名 | 待定（建议：与公众号名称一致的 .com 或 .cn） |
| DNS | Cloudflare（免费，支持CDN加速） |
| SSL | Let's Encrypt 自动续期 |

---

## 3. 数据采集层

### 3.1 changedetection.io（政府网站监控）

**用途**：监控全部31个省级文旅厅 + 文旅部官网的"通知公告"/"政策法规"页面。

**配置要点**：

| 配置项 | 值 | 说明 |
|--------|---|------|
| 检查频率 | 每4小时 | 避免频率过高被封IP |
| 选择器 | CSS Selector | 只监控页面的"通知列表"区域，忽略其他 |
| 浏览器引擎 | Playwright | 处理JS动态渲染的政府网站 |
| 通知方式 | JSON文件 / Webhook | 有变更时写入本地文件或触发HTTP回调 |

**监控目标（全覆盖）**：

共32个监控任务（文旅部 + 31个省级行政区），完整列表见 PRD 第6.1节。

**分批上线策略**：

| 批次 | 范围 | 说明 |
|------|------|------|
| 第1批 | 文旅部 + 数据公开度★★★★以上的省份（约12个） | 数据公开度高，CSS选择器调试较容易 |
| 第2批 | 数据公开度★★★的省份（约16个） | 在第1批稳定后逐步加入 |
| 第3批 | 数据公开度★★及以下（约4个） | 部分省份可能网站结构复杂或更新很少 |

**CSS选择器配置示例**：

```python
# src/config.py 中的部分配置示例
MONITOR_TARGETS = {
    "mct_gov": {
        "name": "文化和旅游部",
        "url": "https://zwgk.mct.gov.cn/zfxxgkml/zcfg/",
        "selector": ".news-list li",  # 需实际调试
        "check_interval": 14400,  # 4小时 = 14400秒
    },
    "beijing": {
        "name": "北京市文化和旅游局",
        "url": "https://whlyj.beijing.gov.cn/zwgk/tzgg/",
        "selector": ".listBox li",
        "check_interval": 14400,
    },
    # ... 其余30个省份
}
```

**已知风险**：

- 政府网站改版可能导致CSS选择器失效 → 每周检查一次监控状态
- 部分网站有反爬机制（验证码、IP限制）→ 配置代理或降低频率
- 每个网站独立监控任务，便于逐个调试和维护

### 3.2 公众号文章采集

**核心挑战**：微信公众号是封闭系统，无官方API读取他人公众号内容。

**推荐方案（分层策略）**：

| 层级 | 工具 | 职责 | 稳定性 |
|------|------|------|--------|
| 内容发现 | 今天看啥（jintiankansha.me）VIP | 将目标公众号转为RSS源 | 中高 |
| 内容获取 | Python脚本（feedparser + requests） | 解析RSS获取文章URL → 抓取正文 | 中高 |
| 内容处理 | LLM API | 摘要、分类、关键词提取 | 高 |
| 人工兜底 | 手动浏览 + 脚本处理 | RSS方案失效时的降级方案 | 高 |

**Python采集逻辑**：

```python
# src/collectors/rss.py 伪代码
import feedparser
import requests
from bs4 import BeautifulSoup

def fetch_wechat_articles(rss_url: str) -> list[dict]:
    """从今天看啥RSS源获取公众号新文章"""
    feed = feedparser.parse(rss_url)
    articles = []
    for entry in feed.entries:
        article = {
            "title": entry.title,
            "url": entry.link,
            "published": entry.published,
            "source": feed.feed.title,
            "content": extract_content(entry.link),
        }
        articles.append(article)
    return articles

def extract_content(url: str) -> str:
    """提取文章正文文本，含降级处理"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://mp.weixin.qq.com/",
    }
    try:
        resp = requests.get(url, timeout=15, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        content_div = soup.select_one("#js_content")
        return content_div.get_text(strip=True) if content_div else ""
    except Exception as e:
        log.warning(f"文章正文提取失败 ({url}): {e}")
        return ""  # 降级：使用RSS feed自带的摘要
```

**RSS源配置**：

```python
# src/config.py
RSS_FEEDS = {
    # A类：官方权威（12个）
    "文旅之声": "https://jintiankansha.me/rss/xxx1",
    "中国旅游研究院": "https://jintiankansha.me/rss/xxx2",
    "中国旅游报": "https://jintiankansha.me/rss/xxx3",
    # ... 完整50个公众号（见PRD第6.2节）

    # 行业媒体RSS（非公众号来源）
    "环球旅讯": "https://rsshub/xxx",
    # ...
}
```

**降级策略**：

1. 今天看啥RSS正常 → 全自动采集
2. RSS部分失效 → 对失效源启用手动采集模式
3. RSS全面失效 → 每天15分钟手动浏览关键公众号，复制到手动输入接口

**法律风险提示**：不大段摘录原文，以原创分析为主体，引用时标注来源。

### 3.3 RSSHub（其他平台监控）

**用途**：监控已有RSS支持的行业媒体和数据平台。

- 自部署在同一台服务器
- 主要用于环球旅讯、品橙旅游等行业媒体
- 部分政府网站如有RSSHub现成路由也可使用
- 作为公众号RSS的补充源

### 3.4 手动输入接口

提供一个简单的命令行/脚本接口，用于运营者手动添加信息源：

```bash
# 手动添加一条信息
python src/manual_input.py \
  --title "云南省发布2026年文旅补贴政策" \
  --url "https://..." \
  --source "手动输入" \
  --category "政策动态"
```

---

## 4. 处理层：Python脚本

### 4.1 日报生成主流程

**入口文件**：`src/main.py`
**触发方式**：cron定时任务（每天 06:30 Asia/Shanghai）

**日报时间线**：

```
06:30  cron触发日报生成脚本
  ↓
06:30-07:00  数据采集 → 去重 → AI分类 → 格式化 → 质量检查
  ↓
07:00  日报草稿生成完毕，保存到公众号草稿箱
  ↓
07:30  如果此时仍未完成 → 触发告警
  ↓
08:00  公众号推送（Phase 1人工确认，Phase 2自动发布）
```

```
# crontab -e
30 6 * * * cd /opt/travel-data-briefing && /opt/travel-data-briefing/venv/bin/python src/main.py daily 2>&1 >> logs/daily.log
```

**主流程步骤**：

```python
# src/main.py 主流程（伪代码）

def generate_daily_briefing():
    """日报生成主流程"""

    # 1. 数据采集
    raw_items = []
    raw_items += collectors.changedetection.fetch_changes(since_hours=24)
    raw_items += collectors.rss.fetch_all_feeds()
    log.info(f"采集到 {len(raw_items)} 条原始数据")

    # 2. 去重
    new_items = processors.deduplicator.filter_new(raw_items)
    log.info(f"去重后剩余 {len(new_items)} 条新数据")

    # 3. AI分类与摘要
    classified = []
    for item in new_items:
        result = processors.classifier.classify_and_summarize(item)
        if result["category"] != "不相关" and result["relevance_score"] >= 5:
            classified.append(result)
    log.info(f"有效条目 {len(classified)} 条")

    # 4. 记忆系统更新
    memory.events.record_reported(classified)
    memory.topics.update_heat(classified)
    memory.sources.update_quality(raw_items, classified)

    # 5. 格式化日报
    briefing_md = processors.formatter.render_daily(classified)

    # 6. 质量检查
    quality_ok, issues = quality_check(briefing_md, classified)
    if not quality_ok:
        alert.send(f"日报质量检查未通过: {issues}")
        # 保存草稿，等待人工处理
        save_draft(briefing_md)
        return

    # 7. 发布
    publishers.wechat.publish_draft(briefing_md)  # 公众号草稿
    publishers.website.generate_page(briefing_md)  # 网站Markdown文件

    # 8. 归档
    db.save_briefing(date=today(), content=briefing_md, items=classified)
    log.info("日报生成完成")
```

### 4.2 AI分类与摘要

**模型调用**：

```python
# src/processors/classifier.py

import os
from openai import OpenAI  # DeepSeek 兼容 OpenAI SDK

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com/v1",
)

CLASSIFY_PROMPT = """你是一个文旅行业分析助手。请对以下内容进行处理：

标题：{title}
正文摘要：{content_snippet}
来源：{source}

请输出JSON格式：
{{
  "category": "政策动态|数据快报|行业热点|不相关",
  "summary": "一句话摘要（不超过50字）",
  "relevance_score": 1-10,
  "province": "涉及的省份，如有",
  "key_numbers": "关键数字，如有"
}}

评判标准：
- 政策动态：政府发布的文旅相关政策、通知、公告
- 数据快报：含具体数字的行业数据（游客量、收入、价格等）
- 行业热点：文旅行业重要事件、企业动态、市场变化
- 不相关：与文旅行业无关的内容

如果内容与文旅行业不相关，category填"不相关"。
注意：只描述已发生的事实和数据，不要生成任何预测性或展望性内容。"""


def classify_and_summarize(item: dict) -> dict:
    """对单条内容进行AI分类和摘要，含重试和错误处理"""
    content_snippet = item["content"][:2000]  # 限制输入长度

    for attempt in range(3):  # 最多重试3次
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是文旅行业数据分析专家。"},
                    {
                        "role": "user",
                        "content": CLASSIFY_PROMPT.format(
                            title=item["title"],
                            content_snippet=content_snippet,
                            source=item["source"],
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                timeout=30,
            )
            result = json.loads(response.choices[0].message.content)
            # 验证必要字段
            assert "category" in result and "summary" in result
            return result
        except (json.JSONDecodeError, AssertionError, KeyError) as e:
            log.warning(f"AI返回格式异常 (attempt {attempt+1}): {e}")
            if attempt == 2:
                return {"category": "不相关", "summary": "", "relevance_score": 0}
        except Exception as e:
            log.warning(f"API调用失败 (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)  # 指数退避
            if attempt == 2:
                return {"category": "不相关", "summary": "", "relevance_score": 0}
```

**批量处理优化**：

```python
def classify_batch(items: list[dict], batch_size: int = 5) -> list[dict]:
    """批量分类，减少API调用次数。失败时降级为逐条处理。"""
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        try:
            batch_prompt = format_batch_prompt(batch)
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是文旅行业数据分析专家。"},
                    {"role": "user", "content": batch_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                timeout=60,
            )
            batch_results = json.loads(response.choices[0].message.content)
            parsed = batch_results.get("items", [])
            if len(parsed) != len(batch):
                raise ValueError(f"返回{len(parsed)}条，期望{len(batch)}条")
            results.extend(parsed)
        except Exception as e:
            log.warning(f"批量分类失败，降级为逐条处理: {e}")
            for item in batch:
                results.append(classify_and_summarize(item))
    return results
```

### 4.3 日报格式化

```python
# src/processors/formatter.py

from jinja2 import Template
from datetime import date

DAILY_TEMPLATE = Template("""【文旅早知道 · {{ date }}】

{% if policies %}📋 政策动态
{% for item in policies %}- [{{ item.province or '全国' }}] {{ item.summary }}
{% endfor %}{% endif %}
{% if data_points %}📊 数据快报
{% for item in data_points %}- {{ item.summary }}{% if item.key_numbers %}（{{ item.key_numbers }}）{% endif %}
{% endfor %}{% endif %}
{% if hot_topics %}🔥 今日热点
{% for item in hot_topics %}- {{ item.summary }}
{% endfor %}{% endif %}
{% if not policies and not data_points and not hot_topics %}今日无重大更新。

💡 行业小知识：{{ knowledge_tip }}
{% endif %}
数据来源：各省文旅厅官网、行业媒体公众号
""")


def render_daily(classified_items: list[dict]) -> str:
    """将分类后的条目渲染为日报Markdown"""
    policies = [i for i in classified_items if i["category"] == "政策动态"][:3]
    data_points = [i for i in classified_items if i["category"] == "数据快报"][:3]
    hot_topics = [i for i in classified_items if i["category"] == "行业热点"][:2]

    return DAILY_TEMPLATE.render(
        date=date.today().strftime("%Y年%m月%d日"),
        policies=policies,
        data_points=data_points,
        hot_topics=hot_topics,
        knowledge_tip=get_random_knowledge_tip(),
    )
```

### 4.4 公众号发布

**方案A：通过微信公众号API发布（推荐）**

```python
# src/publishers/wechat.py

import os
import requests

class WeChatPublisher:
    """微信公众号发布器"""

    def __init__(self):
        self.app_id = os.environ["WECHAT_APP_ID"]
        self.app_secret = os.environ["WECHAT_APP_SECRET"]
        self._access_token = None

    def get_access_token(self) -> str:
        """获取access_token（有效期2小时，需缓存）"""
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        }
        resp = requests.get(url, params=params).json()
        self._access_token = resp["access_token"]
        return self._access_token

    def create_draft(self, title: str, content_html: str, thumb_media_id: str) -> str:
        """创建草稿"""
        url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={self._access_token}"
        data = {
            "articles": [
                {
                    "title": title,
                    "content": content_html,
                    "thumb_media_id": thumb_media_id,
                    "need_open_comment": 1,
                }
            ]
        }
        resp = requests.post(url, json=data).json()
        return resp.get("media_id")

    def publish(self, media_id: str) -> dict:
        """发布草稿（从草稿箱发布）"""
        url = f"https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token={self._access_token}"
        resp = requests.post(url, json={"media_id": media_id}).json()
        return resp
```

**方案B（降级）**：生成草稿后人工在公众号后台确认发布。Phase 1 建议先用方案B，待流程稳定后切换方案A自动发布。

### 4.5 质量检查机制

**自动检查**：

| 检查项 | 规则 | 处理 |
|--------|------|------|
| 日报长度 | < 150字警告，< 100字告警；> 350字警告，> 500字告警 | 告警时人工审核后发布 |
| 分类为空 | 所有内容都被标记为"不相关" | 告警，可能是AI分类异常 |
| 来源链接 | 检查URL是否可访问 | 不可访问的链接标注"链接已失效" |
| 重复内容 | 查询记忆系统已报道事件库 | 去重，避免反复出现同一条信息 |
| 无内容日 | 没有任何有效条目 | 生成"今日无重大更新" + 行业知识 |

**人工检查**（日常运维）：

- 每天花5分钟快速浏览当日日报输出
- 每周检查一次changedetection.io的监控状态
- 检查今天看啥RSS源的可用性

### 4.6 周报生成流程

**触发方式**：cron定时任务（每周日 18:00，生成初稿供周一发布）

```
# crontab -e
0 18 * * 0 cd /opt/travel-data-briefing && /opt/travel-data-briefing/venv/bin/python src/main.py weekly 2>&1 >> logs/weekly.log
```

**流程步骤**：

```python
# src/main.py 周报流程（伪代码）

def generate_weekly_draft():
    """周报初稿生成"""

    # 1. 聚合本周数据
    week_start, week_end = get_current_week_range()
    weekly_items = db.get_processed_items(week_start, week_end)
    trending = memory.topics.get_sustained_topics(min_days=3)

    # 2. 按板块分组
    policies = [i for i in weekly_items if i["category"] == "政策动态"]
    data_points = [i for i in weekly_items if i["category"] == "数据快报"]
    hot_events = [i for i in weekly_items if i["category"] == "行业热点"]

    # 3. 调用Claude API生成初稿
    draft = generate_weekly_with_claude(
        policies=policies,
        data_points=data_points,
        hot_events=hot_events,
        trending_topics=trending,
    )

    # 4. 保存初稿为Markdown文件，等待人工编辑
    draft_path = save_weekly_draft(draft, week_number=get_week_number())
    alert.send(f"周报初稿已生成: {draft_path}，请编辑后发布")
```

**Claude API调用**：

```python
# src/processors/weekly.py

import anthropic

client = anthropic.Anthropic()  # 使用 ANTHROPIC_API_KEY 环境变量

WEEKLY_PROMPT = open("src/prompts/weekly_draft.txt").read()

def generate_weekly_with_claude(
    policies: list, data_points: list, hot_events: list, trending_topics: list
) -> str:
    """使用Claude Sonnet生成周报初稿"""
    context = format_weekly_context(policies, data_points, hot_events, trending_topics)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": WEEKLY_PROMPT.format(
                    week_range=get_week_range_str(),
                    context=context,
                ),
            }
        ],
    )
    return message.content[0].text
```

**人工编辑流程**：

1. 脚本生成初稿 → 保存为 `drafts/weekly/2026-WXX.md`
2. 运营者打开Markdown文件，使用任意编辑器修改
3. 编辑完成后运行发布脚本：`python src/main.py publish-weekly 2026-W08`
4. 脚本将内容发布到公众号（付费文章）+ 网站（摘要版）

**周报付费文章设置**：

- 前150-300字为免费预览区域（通过HTML注释标记分割点）
- 核心分析内容在付费墙后
- 价格：3-5元/篇（通过公众号付费文章功能设置）

### 4.7 月报生成流程

**触发方式**：每月最后一天 cron 触发数据准备，人工主导写作。

```
# crontab -e
0 18 28-31 * * [ "$(date -d tomorrow +\%d)" = "01" ] && cd /opt/travel-data-briefing && /opt/travel-data-briefing/venv/bin/python src/main.py monthly-prep 2>&1 >> logs/monthly.log
```

**流程步骤**：

```python
def prepare_monthly_report():
    """月报数据准备（自动化部分）"""

    month_start, month_end = get_current_month_range()

    # 1. 聚合本月所有数据
    monthly_items = db.get_processed_items(month_start, month_end)

    # 2. 生成月度统计
    stats = {
        "total_items": len(monthly_items),
        "by_category": count_by_category(monthly_items),
        "by_province": count_by_province(monthly_items),
        "top_topics": memory.topics.get_monthly_top(month_start, month_end),
        "province_activity": memory.provinces.get_activity_report(),
    }

    # 3. 从知识库提取数据指标
    indicators = db.get_data_indicators(month_start, month_end)

    # 4. 调用Claude Opus生成大纲和数据分析初稿
    outline = generate_monthly_outline(stats, indicators)

    # 5. 保存数据包
    save_monthly_package(stats, indicators, outline)
    alert.send("月报数据包已准备就绪，请开始写作")
```

**人工写作流程**：

1. 脚本生成数据包（统计数据、指标、大纲）→ `drafts/monthly/2026-02/`
2. 运营者基于数据包撰写月报（5000-8000字）
3. 使用 Matplotlib/Pillow 生成数据图表（至少3张）
4. 完成后运行发布脚本：`python src/main.py publish-monthly 2026-02`
5. 脚本将内容发布到公众号（付费文章，9.9-19.9元）+ 网站（摘要版）

**图表生成辅助**：

```python
# src/processors/charts.py
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.sans-serif"] = ["SimHei"]  # 中文字体
matplotlib.rcParams["axes.unicode_minus"] = False

def generate_province_chart(province_data: dict, output_path: str):
    """生成省份活跃度柱状图"""
    provinces = list(province_data.keys())
    counts = [v["total"] for v in province_data.values()]
    plt.figure(figsize=(12, 6))
    plt.barh(provinces, counts)
    plt.title("本月各省份文旅信息产出量")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
```

---

## 5. 记忆系统

### 5.1 已报道事件库

```python
# src/memory/events.py

class EventMemory:
    """已报道事件管理 — 去重 + 持续性追踪"""

    def record_reported(self, items: list[dict]):
        """记录已报道的事件"""
        for item in items:
            self.db.execute("""
                INSERT OR IGNORE INTO reported_events
                (event_hash, title, category, province, first_reported, last_seen, mention_count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(event_hash) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    mention_count = mention_count + 1
            """, (hash_event(item), item["summary"], item["category"],
                  item.get("province"), today(), today()))

    def is_already_reported(self, item: dict) -> bool:
        """检查事件是否已在近3天内报道过"""
        row = self.db.execute("""
            SELECT 1 FROM reported_events
            WHERE event_hash = ? AND last_seen >= date('now', '-3 days')
        """, (hash_event(item),)).fetchone()
        return row is not None

    def get_trending_topics(self, min_mentions: int = 3) -> list[dict]:
        """获取持续被多个来源提及的热门话题"""
        return self.db.execute("""
            SELECT title, category, province, mention_count, first_reported, last_seen
            FROM reported_events
            WHERE mention_count >= ? AND last_seen >= date('now', '-7 days')
            ORDER BY mention_count DESC
        """, (min_mentions,)).fetchall()
```

### 5.2 话题热度追踪

```python
# src/memory/topics.py

class TopicTracker:
    """话题热度追踪 — 识别持续性热点 vs 一次性新闻"""

    def update_heat(self, classified_items: list[dict]):
        """更新话题热度"""
        for item in classified_items:
            keywords = extract_keywords(item["summary"])
            for kw in keywords:
                self.db.execute("""
                    INSERT INTO topic_heat (keyword, date, source_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(keyword, date) DO UPDATE SET
                        source_count = source_count + 1
                """, (kw, today()))

    def get_sustained_topics(self, min_days: int = 3) -> list[dict]:
        """获取持续热门话题（连续多天被提及）"""
        return self.db.execute("""
            SELECT keyword, COUNT(DISTINCT date) as days,
                   SUM(source_count) as total_mentions
            FROM topic_heat
            WHERE date >= date('now', '-14 days')
            GROUP BY keyword
            HAVING days >= ?
            ORDER BY total_mentions DESC
        """, (min_days,)).fetchall()
```

### 5.3 来源质量评分

```python
# src/memory/sources.py

class SourceScorer:
    """来源质量评分 — 优化数据源权重"""

    def update_quality(self, raw_items: list[dict], useful_items: list[dict]):
        """更新来源质量分"""
        source_stats = {}
        for item in raw_items:
            src = item["source"]
            source_stats.setdefault(src, {"total": 0, "useful": 0})
            source_stats[src]["total"] += 1

        for item in useful_items:
            src = item["source"]
            if src in source_stats:
                source_stats[src]["useful"] += 1

        for src, stats in source_stats.items():
            useful_rate = stats["useful"] / stats["total"] if stats["total"] > 0 else 0
            self.db.execute("""
                INSERT INTO source_quality (source_name, date, total_items, useful_items, useful_rate)
                VALUES (?, ?, ?, ?, ?)
            """, (src, today(), stats["total"], stats["useful"], useful_rate))

    def get_low_quality_sources(self, days: int = 7) -> list[dict]:
        """获取连续N天无有价值内容的来源"""
        return self.db.execute("""
            SELECT source_name, SUM(useful_items) as total_useful
            FROM source_quality
            WHERE date >= date('now', ? || ' days')
            GROUP BY source_name
            HAVING total_useful = 0
        """, (f"-{days}",)).fetchall()

    def get_new_source_candidates(self) -> list[str]:
        """从已采集内容中发现频繁被引用但未监控的信息源"""
        # 分析processed_items中的引用来源
        # 如果某个来源被多次引用但不在监控列表中，标记为候选
        pass
```

### 5.4 省份活跃度

```python
# src/memory/provinces.py

class ProvinceTracker:
    """省份数据产出跟踪"""

    def update(self, classified_items: list[dict]):
        """更新省份活跃度"""
        for item in classified_items:
            if item.get("province"):
                self.db.execute("""
                    INSERT INTO province_activity (province, date, item_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(province, date) DO UPDATE SET
                        item_count = item_count + 1
                """, (item["province"], today()))

    def get_activity_report(self) -> dict:
        """获取各省份最近30天的数据产出报告"""
        rows = self.db.execute("""
            SELECT province, SUM(item_count) as total,
                   COUNT(DISTINCT date) as active_days
            FROM province_activity
            WHERE date >= date('now', '-30 days')
            GROUP BY province
            ORDER BY total DESC
        """).fetchall()
        return {row["province"]: dict(row) for row in rows}
```

### 5.5 Phase 2 延期项（PRD已定义，Phase 1不实施）

以下PRD中定义的记忆/自更新能力在Phase 1不实施，明确记录以避免遗漏：

| PRD条目 | Phase 1状态 | 原因 |
|---------|------------|------|
| 用户关注模式（PRD 7.1） | 延期 | Phase 1无用户数据，需公众号后台数据支撑 |
| Prompt自动优化（PRD 7.2） | 延期 | 需要先积累人工编辑历史数据，建议运行3个月后评估 |
| 模板自动迭代（PRD 7.2） | 延期 | 需要先积累用户反馈数据 |
| 行业术语库（PRD 7.3） | 简化实现 | Phase 1用静态JSON文件管理，不入数据库 |
| 参考资料库（PRD 7.3） | 简化实现 | Phase 1用文件目录管理，不入数据库 |

---

## 6. 发布层

### 6.1 静态网站

**技术选型**：Hugo（静态站点生成器）

| 选型理由 | 说明 |
|---------|------|
| 构建速度 | 毫秒级，适合每日更新 |
| 无服务器 | 纯静态文件，Vercel免费托管 |
| Markdown原生支持 | 日报直接以Markdown文件形式存储 |
| SEO友好 | 自动生成sitemap、meta标签 |
| 搜索功能 | 支持 Lunr.js 客户端搜索 |

**自动更新流程**：

```
Python脚本生成日报Markdown
    ↓
写入 site/content/daily/YYYY/MM/DD.md
    ↓
git add + commit + push（脚本自动执行）
    ↓
Vercel 检测到push → 自动构建部署
    ↓
网站更新完成
```

### 6.2 数据存储

**Phase 1：SQLite**

| 理由 | 说明 |
|------|------|
| 简单 | 单文件数据库，无需额外服务 |
| 够用 | 日报数据量小（每天几十条记录） |
| 备份简单 | 复制一个文件即可 |

**数据表设计**：

```sql
-- 原始采集数据
CREATE TABLE raw_items (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,          -- 来源（公众号名/网站名）
    url TEXT,                       -- 原文链接
    title TEXT,                     -- 原标题
    content TEXT,                   -- 原文内容（截断，最多5000字）
    fetched_at DATETIME NOT NULL,   -- 采集时间
    processed BOOLEAN DEFAULT FALSE -- 是否已处理
);

-- AI处理后的结构化数据
CREATE TABLE processed_items (
    id TEXT PRIMARY KEY,
    raw_item_id TEXT REFERENCES raw_items(id),
    category TEXT NOT NULL,         -- 分类（政策动态/数据快报/行业热点）
    summary TEXT NOT NULL,          -- AI摘要
    relevance_score INTEGER,        -- 相关性评分 1-10
    province TEXT,                  -- 相关省份
    key_numbers TEXT,               -- 关键数字
    processed_at DATETIME NOT NULL
);

-- 日报归档
CREATE TABLE daily_briefings (
    id TEXT PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    content_markdown TEXT NOT NULL,
    items_count INTEGER,
    published_wechat BOOLEAN DEFAULT FALSE,
    published_website BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL
);

-- 记忆系统：已报道事件
CREATE TABLE reported_events (
    event_hash TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT,
    province TEXT,
    first_reported DATE NOT NULL,
    last_seen DATE NOT NULL,
    mention_count INTEGER DEFAULT 1
);

-- 记忆系统：话题热度
CREATE TABLE topic_heat (
    keyword TEXT NOT NULL,
    date DATE NOT NULL,
    source_count INTEGER DEFAULT 0,
    PRIMARY KEY (keyword, date)
);

-- 记忆系统：来源质量
CREATE TABLE source_quality (
    source_name TEXT NOT NULL,
    date DATE NOT NULL,
    total_items INTEGER DEFAULT 0,
    useful_items INTEGER DEFAULT 0,
    useful_rate REAL DEFAULT 0,
    PRIMARY KEY (source_name, date)
);

-- 记忆系统：省份活跃度
CREATE TABLE province_activity (
    province TEXT NOT NULL,
    date DATE NOT NULL,
    item_count INTEGER DEFAULT 0,
    PRIMARY KEY (province, date)
);

-- 知识库：政策文件
CREATE TABLE policy_archive (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    province TEXT,
    policy_type TEXT,               -- 法规/通知/公告/意见
    publish_date DATE,
    summary TEXT,
    full_text TEXT,
    source_url TEXT,
    created_at DATETIME NOT NULL
);

-- 知识库：数据指标
CREATE TABLE data_indicators (
    id TEXT PRIMARY KEY,
    indicator_name TEXT NOT NULL,   -- 游客量/收入/RevPAR等
    province TEXT,
    period TEXT,                    -- 2026-01 / 2026-Q1 / 2025
    value REAL,
    unit TEXT,                      -- 万人次/亿元/元
    yoy_change REAL,               -- 同比变化%
    source TEXT,
    created_at DATETIME NOT NULL
);

-- 周报/月报草稿与发布记录
CREATE TABLE report_drafts (
    id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,      -- weekly / monthly
    period TEXT NOT NULL,           -- 2026-W08 / 2026-02
    draft_markdown TEXT,
    final_markdown TEXT,
    status TEXT DEFAULT 'draft',    -- draft / editing / published
    published_wechat BOOLEAN DEFAULT FALSE,
    published_website BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL,
    published_at DATETIME
);

-- 数据库版本管理
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME NOT NULL,
    description TEXT
);
INSERT INTO schema_version (version, applied_at, description)
VALUES (1, datetime('now'), '初始schema');
```

---

## 7. AI处理规格

### 7.1 模型选择

| 用途 | 模型 | 原因 |
|------|------|------|
| 日报分类+摘要 | DeepSeek V3 | 成本最低（~0.002元/条），中文质量好，兼容OpenAI SDK |
| 周报初稿 | Claude API (Sonnet) | 分析深度和逻辑推理能力强 |
| 月报辅助 | Claude API (Opus) | 深度分析场景，质量优先 |
| 备选 | GLM-4 / Qwen | 国内模型，网络延迟更低 |

### 7.2 Prompt管理

所有Prompt以模板文件存储在 `src/prompts/` 目录，版本管理。

```
src/prompts/
├── classify.txt          # 日报分类+摘要
├── daily_summary.txt     # 日报总结（无内容日知识生成）
├── weekly_draft.txt      # 周报初稿生成
├── monthly_outline.txt   # 月报大纲生成
└── policy_interpret.txt  # 政策解读（周报用）
```

**Prompt原则**：

- 所有Prompt必须明确输出格式（JSON）
- 必须包含"如果不相关则标记为不相关"的指令
- 必须限制输出长度
- 不做任何预测/展望类生成

### 7.3 成本控制

| 措施 | 说明 |
|------|------|
| 预过滤 | 在调用AI前，先用关键词过滤明显不相关的内容 |
| 批量处理 | 多条内容合并为一次API调用（减少请求次数） |
| 缓存 | 相同URL的内容不重复分析 |
| 模型分级 | 日常用DeepSeek，深度分析用Claude |
| 内容截断 | 输入内容限制在2000字以内 |

**预估月度成本**：

| 项目 | 日调用量 | 单价估算 | 月成本 |
|------|---------|---------|--------|
| DeepSeek日报分类 | ~100条/天 | ~0.002元/条 | ~6元 |
| Claude周报初稿 | 4次/月 | ~0.5元/次 | ~2元 |
| Claude月报辅助 | 1次/月 | ~2元/次 | ~2元 |
| **API总计** | | | **~10元/月** |

---

## 8. 项目目录结构

```
travel-data-briefing/
├── docs/                              # 项目文档
│   ├── PRD.md                         # 产品需求文档
│   ├── SPEC.md                        # 技术规格文档
│   ├── competitive-analysis.md        # 竞品分析
│   └── plans/                         # 设计决策记录
│       └── 2026-02-19-design-decisions.md
│
├── site/                              # Hugo网站源码
│   ├── content/
│   │   ├── daily/                     # 日报内容（按年/月组织）
│   │   │   └── 2026/02/20.md
│   │   ├── weekly/                    # 周报摘要
│   │   └── monthly/                   # 月报摘要
│   ├── layouts/
│   ├── static/
│   └── config.toml
│
├── src/                               # Python源码
│   ├── collectors/                    # 数据采集模块
│   │   ├── __init__.py
│   │   ├── changedetection.py         # changedetection.io API客户端
│   │   ├── rss.py                     # RSS源采集（今天看啥 + RSSHub）
│   │   └── manual.py                  # 手动输入接口
│   │
│   ├── processors/                    # 数据处理模块
│   │   ├── __init__.py
│   │   ├── deduplicator.py            # 去重（基于URL哈希 + 记忆系统）
│   │   ├── classifier.py             # AI分类+摘要（LLM API调用）
│   │   ├── formatter.py              # 日报Markdown渲染（Jinja2）
│   │   ├── weekly.py                  # 周报初稿生成（Claude API）
│   │   ├── monthly.py                 # 月报数据准备（Claude API）
│   │   └── charts.py                  # 数据图表生成（Matplotlib）
│   │
│   ├── publishers/                    # 发布模块
│   │   ├── __init__.py
│   │   ├── wechat.py                  # 公众号API客户端
│   │   └── website.py                 # Hugo内容生成 + git push
│   │
│   ├── memory/                        # 记忆系统
│   │   ├── __init__.py
│   │   ├── events.py                  # 已报道事件管理
│   │   ├── topics.py                  # 话题热度追踪
│   │   ├── sources.py                 # 来源质量评分
│   │   └── provinces.py               # 省份活跃度
│   │
│   ├── db/                            # 数据库
│   │   ├── __init__.py
│   │   ├── models.py                  # 数据库初始化和迁移
│   │   └── queries.py                 # 常用查询
│   │
│   ├── prompts/                       # AI提示词模板
│   │   ├── classify.txt
│   │   ├── weekly_draft.txt
│   │   ├── monthly_outline.txt
│   │   └── policy_interpret.txt
│   │
│   ├── config.py                      # 配置管理（监控目标、RSS源等）
│   ├── main.py                        # 主入口（daily/weekly/monthly子命令）
│   └── alert.py                       # 告警通知
│
├── tests/                             # 测试
│   ├── test_collectors.py
│   ├── test_processors.py
│   ├── test_memory.py
│   └── test_formatter.py
│
├── data/                              # 运行时数据（不入Git）
│   ├── briefing.db                    # SQLite数据库
│   ├── drafts/                        # 周报/月报草稿
│   │   ├── weekly/
│   │   └── monthly/
│   ├── knowledge/                     # 知识库文件（Phase 1简化实现）
│   │   ├── terminology.json           # 行业术语库
│   │   └── references/                # 参考资料目录
│   ├── logs/                          # 运行日志
│   └── backups/                       # 数据库备份
│
├── docker-compose.yml                 # changedetection + RSSHub
├── requirements.txt                   # Python依赖
├── .env.example                       # 环境变量模板
└── .gitignore
```

---

## 9. 运维与监控

### 9.1 告警机制

| 监控项 | 告警条件 | 通知方式 |
|--------|---------|---------|
| 日报生成脚本执行失败 | 主流程抛出未捕获异常 | 企业微信webhook / 邮件 |
| changedetection.io无变更 | 某个网站连续7天无变更 | 来源质量评分自动标记 |
| RSS源不可用 | 连续3次拉取失败 | 告警通知 + 自动降级 |
| 服务器磁盘空间 | 使用率 > 80% | 系统告警 |
| 日报未按时生成 | 07:30前未完成 | 告警 + 保存草稿 |
| AI API调用异常 | 连续失败或费用异常 | 立即告警 |

**告警实现**：

```python
# src/alert.py
import os
import requests

def send_alert(message: str):
    """发送告警到企业微信"""
    webhook_url = os.environ.get("WECHAT_WORK_WEBHOOK")
    if webhook_url:
        requests.post(webhook_url, json={
            "msgtype": "text",
            "text": {"content": f"[文旅数据简报] {message}"}
        })
    # 同时写入日志
    logging.error(f"ALERT: {message}")
```

### 9.2 备份策略

| 数据 | 备份方式 | 频率 |
|------|---------|------|
| SQLite数据库 | 复制到云存储 / 本地冗余 | 每日（cron） |
| 网站内容（Markdown） | Git仓库 | 每日（自动commit） |
| Docker配置 | Git仓库 | 每次修改后 |
| Prompt模板 | Git仓库 | 每次修改后 |

### 9.3 日常运维清单

| 任务 | 频率 | 内容 |
|------|------|------|
| 检查日报质量 | 每天 | 快速浏览当日输出，确认无明显错误 |
| 检查今天看啥RSS | 每周 | 确认RSS源正常，续费VIP |
| 检查changedetection | 每周 | 确认监控任务正常运行 |
| 查看来源质量报告 | 每周 | 检查记忆系统标记的低质量源 |
| 处理告警 | 不定期 | 响应自动告警 |

周报编辑和月报写作不算在运维内，属于内容生产。

---

## 10. 安全考虑

### 10.1 服务器安全

- SSH密钥登录，禁用密码登录
- 防火墙只开放必要端口（80, 443, SSH）
- Docker容器使用非root用户运行
- 定期更新系统和Docker镜像

### 10.2 密钥管理

所有密钥通过环境变量管理，不写入代码：

```bash
# .env.example
DEEPSEEK_API_KEY=             # DeepSeek API密钥
ANTHROPIC_API_KEY=            # Claude API密钥
WECHAT_APP_ID=                # 公众号AppID
WECHAT_APP_SECRET=            # 公众号AppSecret
WECHAT_WORK_WEBHOOK=          # 企业微信告警webhook
CHANGEDETECTION_API_KEY=      # changedetection.io API密钥
```

### 10.3 数据安全

- SQLite数据库文件权限设置为600
- 备份数据加密存储
- 不存储任何用户个人信息（Phase 1无用户系统）
- 公众号文章只存储摘要，不大段保存原文

---

## 11. 扩展性考虑（Phase 2+）

以下内容在Phase 1不实施，但在架构设计时预留能力：

| 扩展方向 | 当前预留 |
|---------|---------|
| 订阅制付费 | 内容生产流程不变，增加发布渠道即可 |
| B端报告定制 | 月报框架可复用，增加区域/主题筛选参数 |
| 数据库升级 | SQLite可迁移到PostgreSQL（表结构已规范化） |
| 搜索功能增强 | Hugo支持Lunr.js客户端搜索 |
| Prompt自动优化 | 记忆系统已记录人工修改率，可自动调整Prompt |
| 新来源自动发现 | 来源质量评分模块已预留接口 |

---

## 12. 待确认事项

| 序号 | 事项 | 优先级 | 状态 |
|------|------|--------|------|
| 1 | 公众号名称确定 | P0 | 待定 |
| 2 | 域名注册 | P0 | 待定 |
| 3 | 腾讯云服务器购买 | P0 | 待定 |
| 4 | DeepSeek API注册和充值 | P0 | 待定 |
| 5 | 今天看啥VIP注册和RSS源配置 | P0 | 待验证 |
| 6 | 各省文旅厅网站的具体CSS选择器调试 | P1 | 待实施 |
| 7 | 公众号API发布方案验证 | P1 | 待验证 |
| 8 | Hugo主题选择 | P2 | 待定 |
| 9 | 小红书/抖音引流账号注册 | P2 | 待定 |
