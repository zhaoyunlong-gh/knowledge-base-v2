"""测试 HackerNewsCollector"""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pipeline.hacker_news_collector import HackerNewsCollector


class TestHackerNewsCollector:
    """HackerNewsCollector 测试"""

    @pytest.fixture
    def temp_raw_dir(self, tmp_path):
        """创建临时 raw 目录"""
        raw_dir = tmp_path / "knowledge" / "raw"
        raw_dir.mkdir(parents=True)
        return raw_dir

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        return {
            "api_url": "https://hn.algolia.com/api/v1/search",
            "keywords": ["LLM", "RAG", "agent", "MCP"],
            "batch_size": 50,
            "query": "AI OR LLM OR agent",
        }

    @pytest.fixture
    def sample_hn_response(self):
        """Sample HN API response"""
        return {
            "hits": [
                {
                    "id": 12345678,
                    "title": "Show HN: I built an AI agent with LLM capabilities",
                    "url": "https://news.ycombinator.com/item?id=12345678",
                    "points": 200,
                    "author": "testuser",
                    "created_at_i": 1715500000,
                    "num_comments": 45,
                },
                {
                    "id": 87654321,
                    "title": "Understanding RAG systems",
                    "url": "https://example.com/rag",
                    "points": 150,
                    "author": "ai_researcher",
                    "created_at_i": 1715400000,
                    "num_comments": 30,
                },
                {
                    "id": 11111111,
                    "title": "Python tips and tricks",
                    "url": "https://example.com/python",
                    "points": 50,
                    "author": "coder",
                    "created_at_i": 1715300000,
                    "num_comments": 10,
                },
            ]
        }

    def test_format_item(self, mock_config):
        """测试格式化 HN 文章数据"""
        collector = HackerNewsCollector(mock_config)

        raw_item = {
            "id": 12345678,
            "title": "Test article about LLM",
            "url": "https://news.ycombinator.com/item?id=12345678",
            "points": 100,
            "author": "testuser",
            "created_at_i": 1715500000,
            "num_comments": 25,
        }

        formatted = collector.format([raw_item])[0]

        assert formatted["id"] == "hn-12345678"
        assert formatted["signal_type"] == "hacker-news"
        assert formatted["title"] == "Test article about LLM"
        assert formatted["points"] == 100
        assert formatted["author"] == "testuser"
        assert formatted["comments"] == 25
        assert formatted["created_at"] is not None

    def test_filter_by_keywords(self, mock_config):
        """测试关键词过滤"""
        collector = HackerNewsCollector(mock_config)

        items = [
            {"title": "Show HN: I built an AI agent with LLM"},
            {"title": "Understanding RAG systems"},
            {"title": "Python tips and tricks"},
        ]

        filtered = collector.filter_by_keywords(items)

        assert len(filtered) == 2
        assert any("LLM" in item["title"] for item in filtered)
        assert any("RAG" in item["title"] for item in filtered)
        assert not any("Python" in item["title"] for item in filtered)

    def test_append_to_raw_new_file(self, mock_config, temp_raw_dir):
        """测试创建新的 raw 文件"""
        collector = HackerNewsCollector(mock_config)

        with patch("pipeline.hacker_news_collector.Path") as mock_path:
            mock_path.return_value = temp_raw_dir

            items = [
                {
                    "id": "hn-12345678",
                    "title": "Test article",
                    "url": "https://news.ycombinator.com/item?id=12345678",
                    "points": 100,
                    "author": "testuser",
                    "created_at": "2026-05-12T10:00:00Z",
                    "comments": 25,
                    "signal_type": "hacker-news",
                }
            ]

            raw_file = collector.append_to_raw(items, "2026-05-12")

            assert Path(raw_file).exists()
            with open(raw_file, "r") as f:
                data = json.load(f)
                assert data["source"] == "hacker-news"
                assert data["count"] == 1
                assert len(data["items"]) == 1

    def test_append_to_raw_deduplication(self, mock_config, temp_raw_dir):
        """测试 URL 去重"""
        collector = HackerNewsCollector(mock_config)

        existing_data = {
            "source": "hacker-news",
            "collected_at": "2026-05-12T08:00:00Z",
            "query": "AI OR LLM OR agent",
            "count": 1,
            "items": [
                {
                    "id": "hn-12345678",
                    "title": "Existing article",
                    "url": "https://news.ycombinator.com/item?id=12345678",
                    "points": 100,
                    "author": "testuser",
                    "created_at": "2026-05-12T08:00:00Z",
                    "comments": 25,
                    "signal_type": "hacker-news",
                }
            ],
        }

        existing_file = temp_raw_dir / "hacker-news-2026-05-12.json"
        with open(existing_file, "w") as f:
            json.dump(existing_data, f)

        with patch("pipeline.hacker_news_collector.Path") as mock_path:
            mock_path.return_value = temp_raw_dir

            new_items = [
                {
                    "id": "hn-12345678",
                    "title": "Duplicate article",
                    "url": "https://news.ycombinator.com/item?id=12345678",
                    "points": 150,
                    "author": "anotheruser",
                    "created_at": "2026-05-12T10:00:00Z",
                    "comments": 50,
                    "signal_type": "hacker-news",
                }
            ]

            raw_file = collector.append_to_raw(new_items, "2026-05-12")

            with open(raw_file, "r") as f:
                data = json.load(f)
                assert data["count"] == 1
                assert data["items"][0]["points"] == 100

    def test_rate_limit_retry(self, mock_config):
        """测试 rate limit 重试逻辑"""
        collector = HackerNewsCollector(mock_config)

        # First call returns 429, second returns 200 with hits
        responses = [
            Mock(status_code=429),
            Mock(status_code=200, json=lambda: {"hits": [{"id": 1, "title": "Test"}]}),
        ]

        with patch("pipeline.hacker_news_collector.requests.get") as mock_get:
            mock_get.side_effect = responses

            result = collector.fetch()

            assert mock_get.call_count == 2
            assert len(result) == 1

    def test_fetch_empty_response(self, mock_config):
        """测试空响应处理"""
        collector = HackerNewsCollector(mock_config)

        with patch("pipeline.hacker_news_collector.requests.get") as mock_get:
            mock_get.return_value = Mock(
                status_code=200, json=lambda: {"hits": []}
            )

            result = collector.fetch()
            assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])