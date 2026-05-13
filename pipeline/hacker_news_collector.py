"""Hacker News 数据采集器 - 使用 Algolia HN API"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import requests


KEYWORD_WHITELIST = ["LLM", "RAG", "fine-tuning", "agent", "MCP"]


class HackerNewsCollector:
    """从 Hacker News 获取 AI 相关文章的采集器"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.api_url = self.config.get("api_url", "https://hn.algolia.com/api/v1/search")
        self.keywords = self.config.get("keywords", KEYWORD_WHITELIST)
        self.batch_size = self.config.get("batch_size", 50)
        self.query = self.config.get("query", "AI OR LLM OR agent OR machine-learning")

    def fetch(self) -> List[Dict]:
        """获取 HN 文章

        Returns:
            HN 文章列表
        """
        print(f"[HackerNewsCollector] Starting HN data collection...")

        params = {
            "query": self.query,
            "tags": "story",
            "hitsPerPage": self.batch_size,
        }

        for attempt in range(3):
            try:
                response = requests.get(self.api_url, params=params, timeout=30)
                if response.status_code == 429:
                    print(f"[HackerNewsCollector] Rate limit hit, waiting 1s before retry...")
                    time.sleep(1)
                    continue
                response.raise_for_status()
                data = response.json()
                articles = data.get("hits", [])
                print(f"[HackerNewsCollector] Fetched {len(articles)} articles from HN")
                return articles

            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    print(f"[HackerNewsCollector] Collection failed: {e}")
                    return []
                time.sleep(1)

        return []

    def format(self, items: List[Dict]) -> List[Dict]:
        """格式化 HN 文章数据

        Args:
            items: 原始 HN 文章列表

        Returns:
            格式化后的文章列表
        """
        formatted = []
        for item in items:
            formatted_item = {
                "id": f"hn-{item.get('objectID', item.get('id', ''))}",
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "points": item.get("points", 0),
                "author": item.get("author", ""),
                "created_at": datetime.fromtimestamp(item.get("created_at_i", 0)).isoformat() + "Z" if item.get("created_at_i") else None,
                "comments": item.get("num_comments", 0),
                "signal_type": "hacker-news",
            }
            formatted.append(formatted_item)
        return formatted

    def filter_by_keywords(self, items: List[Dict]) -> List[Dict]:
        """根据关键词过滤文章

        Args:
            items: 格式化后的文章列表

        Returns:
            过滤后的文章列表
        """
        filtered = []
        for item in items:
            title_lower = item.get("title", "").lower()
            if any(kw.lower() in title_lower for kw in self.keywords):
                filtered.append(item)
        print(f"[HackerNewsCollector] Filtered to {len(filtered)} articles matching keywords")
        return filtered

    def append_to_raw(self, items: List[Dict], date: Optional[str] = None) -> str:
        """追加 items 到 raw 文件

        Args:
            items: 文章列表
            date: 日期字符串，默认为今天

        Returns:
            raw 文件路径
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        raw_dir = Path("knowledge/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)

        raw_file = raw_dir / f"hacker-news-{date}.json"

        if raw_file.exists():
            with open(raw_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "source": "hacker-news",
                "collected_at": datetime.utcnow().isoformat() + "Z",
                "query": self.query,
                "count": 0,
                "items": [],
            }

        # 去重：基于 URL
        existing_urls = {item.get("url") for item in data.get("items", [])}
        new_items = [item for item in items if item.get("url") not in existing_urls]

        # 追加新 items
        for item in new_items:
            data["items"].append(item)

        data["count"] = len(data["items"])
        data["collected_at"] = datetime.utcnow().isoformat() + "Z"

        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[HackerNewsCollector] Collected {len(new_items)} items, saved to {raw_file}")
        return str(raw_file)

    def collect(self, count: int = 50, date: Optional[str] = None) -> str:
        """执行完整采集流程

        Args:
            count: 获取文章数量
            date: 日期字符串

        Returns:
            raw 文件路径
        """
        print(f"[HackerNewsCollector] Fetching top {count} HN AI articles...")

        articles = self.fetch()
        if not articles:
            print("[HackerNewsCollector] No articles fetched")
            return ""

        formatted = self.format(articles)
        filtered = self.filter_by_keywords(formatted)

        if not filtered:
            print("[HackerNewsCollector] No articles after keyword filtering")
            return ""

        raw_file = self.append_to_raw(filtered, date)
        print(f"[HackerNewsCollector] Saved to {raw_file}")

        return raw_file