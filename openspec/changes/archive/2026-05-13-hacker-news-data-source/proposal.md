## Why

知识库现有 GitHub Trending 数据源只能反映项目热度（star 增长），无法捕捉技术社区的实时讨论热度。Hacker News 是 AI 技术从业者关注的重要社区，增加 HN 数据源可以实现多维度热点发现——项目热度 + 社区讨论。

## What Changes

- 新增 Hacker News 数据采集器，使用 Algolia HN API
- 数据存入 `knowledge/raw/hacker-news-{date}.json`
- 关键词白名单过滤（LLM, RAG, fine-tuning, agent, MCP）
- 与现有 GitHub Trending 采集共用同一调度周期
- 配置化管理，数据源参数写在 `rss_sources.yaml`

## Capabilities

### New Capabilities

- `hacker-news-collector`: 从 Algolia HN API 采集 AI 相关文章，支持关键词过滤、数据去重、错误重试

### Modified Capabilities

- `github-collector`: 无需求变更（复用相同架构，不修改现有行为）
- `pipeline-runner`: 无需求变更（HN 采集使用相同调度机制）

## Impact

- **新增文件**: `pipeline/hacker_news_collector.py`
- **修改文件**: `pipeline/rss_sources.yaml`（增加 HN 配置）
- **数据文件**: `knowledge/raw/hacker-news-{date}.json`
- **依赖**: 无外部依赖，使用 Algolia 公开 API（`hn.algolia.com/api/v1/search`）