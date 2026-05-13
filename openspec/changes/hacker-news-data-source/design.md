## Context

知识库 AI 知识采集系统当前从 GitHub Trending 获取项目热度数据，存入 `knowledge/raw/` 目录。现需要增加 Hacker News 作为第二个数据源，捕捉技术社区讨论热度。

**当前架构:**
- `pipeline/collector.py` — GitHub Trending 采集器
- `pipeline/rss_sources.yaml` — 数据源配置
- `pipeline/run.py` — 采集任务入口

**约束:**
- 复用现有 `collector.py` 架构模式
- HN 无官方 API，使用 Algolia 公开 API
- 配置化管理，不硬编码

## Goals / Non-Goals

**Goals:**
- 实现 HN 数据采集，与 GitHub Trending 共用调度
- 数据格式与现有 raw 文件结构一致
- 配置化管理，可通过 yaml 修改参数

**Non-Goals:**
- 不实现 HN 实时推送（暂不需要）
- 不修改 GitHub Trending 采集逻辑
- 不实现复杂的趋势分析（后续 Growth 功能）

## Decisions

### 1. 使用 Algolia HN API 而非爬虫

**决定:** 使用 `https://hn.algolia.com/api/v1/search` 端点

**理由:**
- 官方推荐的搜索 API，稳定性有保障
- 无反爬风险，维护成本低
- 响应格式结构化，易于解析

**替代方案考虑:**
- Firebase 原生 API: 需要长连接，不适合轮询模式
- 直接爬虫: 维护成本高，易被封禁

### 2. 复用 Collector 架构模式

**决定:** 新增 `HackerNewsCollector` 类，与 `Collector` 并列

```python
# pipeline/hacker_news_collector.py
class HackerNewsCollector:
    def __init__(self, config: dict):
        self.api_url = "https://hn.algolia.com/api/v1/search"
        self.keywords = config.get("keywords", [])
        self.batch_size = config.get("batch_size", 50)

    def fetch(self) -> list:
        # 调用 Algolia API 获取数据
        pass

    def format(self, items: list) -> list:
        # 格式化数据，添加 signal_type
        pass

    def append_to_raw(self, items: list, date: str) -> str:
        # 追加到 raw 文件
        pass
```

**理由:**
- 与现有架构保持一致
- 便于后续扩展更多数据源
- 测试模式可复用

### 3. 数据模型设计

**决定:** HN 数据使用与 GitHub Trending 相同的 raw 文件结构

```json
{
  "source": "hacker-news",
  "collected_at": "2026-05-12T10:00:00Z",
  "query": "AI OR LLM OR agent",
  "count": 50,
  "items": [...]
}
```

**理由:**
- 统一的数据格式便于后续处理
- 与现有 `organizer.py` 逻辑兼容

### 4. 关键词过滤策略

**决定:** 在客户端过滤，非服务端搜索

查询参数使用宽泛关键词 `"AI OR LLM OR agent OR machine-learning"`，然后在代码中用白名单过滤：

```python
KEYWORD_WHITELIST = ["LLM", "RAG", "fine-tuning", "agent", "MCP"]

def filter_by_keywords(items: list) -> list:
    return [
        item for item in items
        if any(kw.lower() in item["title"].lower() for kw in KEYWORD_WHITELIST)
    ]
```

**理由:**
- Algolia 搜索语法有限，客户端过滤更精准
- 白名单可配置，适应业务变化

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Algolia 免费 tier QPS 限制 | 设置请求间隔 1 秒，单次请求 50 条 |
| API 格式变更 | 单元测试覆盖 + 错误日志 |
| 数据去重不完整 | 基于 URL 去重，同一 URL 不重复采集 |

## Migration Plan

1. **Phase 1**: 创建 `pipeline/hacker_news_collector.py`，实现基础采集逻辑
2. **Phase 2**: 修改 `pipeline/rss_sources.yaml`，增加 HN 配置段
3. **Phase 3**: 修改 `pipeline/run.py`，集成 HN 采集到调度流程
4. **Phase 4**: 添加测试桩 `tests/pipeline/test_hacker_news_collector.py`

**回滚策略:** 如 HN 采集失败，不影响 GitHub Trending 任务执行——两者独立运行

## Open Questions

- 是否需要实现增量采集（只采集新增内容）？当前为全量每日采集
- HN 数据是否需要与 GitHub Trending 数据合并展示？（后续功能）