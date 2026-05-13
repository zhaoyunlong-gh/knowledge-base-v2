---
stepsCompleted: ["step-01-init", "step-02-discovery", "step-02c-executive-summary", "step-03-success", "step-04-journeys", "step-05-domain-skipped", "step-06-innovation-skipped", "step-07-project-type", "step-08-scoping"]
inputDocuments: []
workflowType: 'prd'
classification:
  projectType: API/数据采集管道
  domain: AI技术资讯聚合
  complexity: 低-中
  projectContext: 绿色字段
  focus: 技术趋势追踪
---

# Product Requirements Document - knowledge-base-v2

**Author:** Imaxc
**Date:** 2026-05-12

## Executive Summary

### 产品愿景

为知识库构建多源热点发现系统，整合 GitHub Trending 和 Hacker News，让用户（产品/市场人员）能快速感知 AI 技术社区的最新动态。

核心用户需求：**知道发生了什么** — 热点发现优先于深度分析。

**解决的问题：**
- 现有 GitHub Trending 只反映项目热度（star 增长），无法捕捉技术社区的讨论热度
- Hacker News 提供社区讨论信号（points + 评论），补充技术话题热度的视角
- 两者结合实现多维度热点发现

### What Makes This Special

**差异化核心：** 多信号融合 + 实时发现

| 数据源 | 信号类型 | 反映维度 |
|---|---|---|
| GitHub Trending | 项目热度 | 技术方案受欢迎程度 |
| Hacker News | 社区讨论 | 技术话题讨论热度 |

两个信号共同指向热点，但捕捉维度不同——不是看数字，是看趋势和社区注意力。

**关键约束：**
- HN 无官方 API，使用 Algolia API 接入
- 数据模型新增 `signal_type` 字段区分来源
- 关键词白名单过滤噪音：`LLM, RAG, fine-tuning, agent, MCP`

## Project Classification

| 维度 | 值 |
|---|---|
| 项目类型 | API / 数据采集管道 |
| 领域 | AI 技术资讯聚合 |
| 复杂度 | 低-中 |
| 场景 | 绿色字段（新功能） |
| 核心目标 | 技术社区热点发现 |

---

## Success Criteria

### User Success

- 数据去重正常：HN 数据与现有 GitHub Trending 数据不重复
- 关键词过滤有效：只保留 AI 相关内容（白名单：`LLM, RAG, fine-tuning, agent, MCP`）
- 数据可读：格式统一，用户能快速扫描热点

### Business Success

- 有数据可用：HN 文章成功采集并存入 `knowledge/raw/hacker-news-{date}.json`
- 多源覆盖：用户能看到 GitHub 和 HN 两个维度的热点
- 数据质量：HN 数据带时间戳归档，支持趋势对比

### Technical Success

- Pipeline 兼容：新增 HN 采集器复用现有 `collector.py` 架构
- 配置化管理：HN 数据源配置在 `rss_sources.yaml`，不硬编码
- Rate limit 保护：接入 Algolia API 配置 rate limit guard
- 可测试：新增 HN 采集器有对应测试桩

## Product Scope

### MVP

- HN Algolia API 接入（搜索 "AI OR LLM OR agent" 等关键词）
- 每日定时采集（与 GitHub Trending 同一调度）
- 数据存入 `knowledge/raw/hacker-news-{date}.json`
- 关键词过滤 + 去重

### Growth (Post-MVP)

- 趋势分析：点数变化监控
- Ask HN / Show HN 分类
- 多数据源统一展示

### Vision

- 实时热点推送
- AI 技术趋势报告生成

---

## User Journeys

### Journey 1: 系统运营者 — 每日数据采集

**角色：** 小明，负责运行每日采集任务
**场景：** 早上到公司，检查昨天的数据采集是否正常

1. 打开 GitHub Actions 日志
2. 确认 HN 数据已采集（查看 `hacker-news-2026-05-12.json`）
3. 如有异常，排查 `rss_sources.yaml` 配置问题
4. 手动触发重跑如果需要

**关键路径：** 定时触发 → 数据入库 → 日志确认
**失败场景：** API 限流 → 重试机制生效 → 记录失败原因

---

### Journey 2: 数据消费者 — 浏览热点

**角色：** 产品经理小李，想了解本周 AI 技术热点

1. 打开知识库 articles/ 目录
2. 浏览 HN 来源的热点文章
3. 看到标题 + 分数，快速判断是否感兴趣
4. 点击链接跳转到原始 HN 讨论

**关键路径：** 浏览 → 筛选 → 点击跳转
**失败场景：** 数据去重不干净 → 重复内容 → 体验下降

---

### Journey 3: 开发者 — 扩展数据源

**角色：** 开发者小王，想增加一个新的数据源（如 RSS）

1. 阅读 `pipeline/collector.py` 了解架构
2. 在 `rss_sources.yaml` 添加新数据源配置
3. 运行本地测试验证
4. 提交 PR 合并

**关键路径：** 阅读文档 → 添加配置 → 本地测试 → 上线
**失败场景：** API 格式变更 → 测试桩未更新 → 采集失败

### Journey Requirements Summary

| Journey | 揭示的需求 |
|---|---|
| 系统运营者 | GitHub Actions 集成、定时任务、错误日志 |
| 数据消费者 | 数据格式标准化、URL 可点击、分数显示 |
| 开发者 | 清晰的代码架构、配置化设计、测试覆盖 |

---

## API/数据采集管道 - 技术规格

### 数据存储结构

参考 GitHub Trending，数据格式：

```json
{
  "source": "hacker-news",
  "collected_at": "2026-05-12T10:00:00Z",
  "query": "AI OR LLM OR agent",
  "count": 50,
  "items": [
    {
      "id": "hn-12345678",
      "title": "Show HN: I built an AI agent that...",
      "url": "https://news.ycombinator.com/item?id=12345678",
      "points": 200,
      "author": "username",
      "created_at": "2026-05-12T08:30:00Z",
      "comments": 45,
      "signal_type": "hacker-news"
    }
  ]
}
```

### 采集规格

| 参数 | 值 |
|---|---|
| 采集频率 | 每日（与 GitHub Trending 同一调度） |
| 批量大小 | 50 条 |
| 存储位置 | `knowledge/raw/hacker-news-{date}.json` |
| 关键词过滤 | `LLM, RAG, fine-tuning, agent, MCP` |

### API 集成 - Algolia HN API

**端点：** `https://hn.algolia.com/api/v1/search`

**查询参数：**
- `query`: `"AI OR LLM OR agent"`
- `tags`: `"story"` (仅文章，不含评论)
- `hitsPerPage`: `50`

### 数据模型字段

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | HN 文章 ID |
| title | string | 文章标题 |
| url | string | HN 讨论链接 |
| points | int | 获得的点数 |
| author | string | 作者名 |
| created_at | datetime | 发布时间 |
| comments | int | 评论数 |
| signal_type | string | 固定值 `"hacker-news"` |

### 错误处理

- API 限流：等待 1 秒后重试，最多 3 次
- 采集失败：记录错误日志，不阻塞后续任务
- 数据验证：检查必要字段，缺失则跳过

---

## Project Scoping

### Strategy & Philosophy

**Approach:** 单次发布，MVP + 明确的后续扩展路径
**Resource Requirements:** 开发者 1 名，参考现有 pipeline 架构

### Complete Feature Set

**Core User Journeys Supported:**
- 系统运营者：每日定时采集 + 监控
- 数据消费者：浏览 HN 热点文章
- 开发者：扩展新的数据源

**Must-Have (MVP):**
- HN Algolia API 接入
- 每日定时采集（与 GitHub Trending 同一调度）
- 数据存入 `knowledge/raw/hacker-news-{date}.json`
- 关键词过滤 + 去重
- 可测试（测试桩）

**Nice-to-Have (Post-MVP):**
- 趋势分析：点数变化监控
- Ask HN / Show HN 分类
- 多数据源统一展示
- 实时热点推送
- AI 技术趋势报告生成

### Risk Mitigation

| 风险 | 缓解方案 |
|---|---|
| Algolia API 限流 | Rate limit guard + 重试机制 |
| 数据格式变更 | 测试桩覆盖 + 错误日志 |
| 采集失败 | 不阻塞 GitHub Trending 任务，独立运行 |

---

## Functional Requirements

（待 Step 9 定义）