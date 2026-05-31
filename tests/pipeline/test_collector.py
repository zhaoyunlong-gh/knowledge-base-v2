"""测试 Collector"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pipeline.collector import Collector, QUERY


class TestCollector:
    """Collector 测试"""

    @pytest.fixture
    def collector(self):
        """创建带 token 的 Collector"""
        return Collector(token="test-token")

    @pytest.fixture
    def collector_no_token(self):
        """创建无 token 的 Collector"""
        with patch.dict(os.environ, {}, clear=True):
            return Collector(token=None)

    @pytest.fixture
    def sample_graphql_response(self):
        """Sample GitHub GraphQL response"""
        return {
            "data": {
                "search": {
                    "nodes": [
                        {
                            "nameWithOwner": "user/ai-project",
                            "name": "ai-project",
                            "description": "An AI agent framework",
                            "url": "https://github.com/user/ai-project",
                            "stargazerCount": 1500,
                            "primaryLanguage": {"name": "Python"},
                            "repositoryTopics": {
                                "nodes": [
                                    {"topic": {"name": "ai"}},
                                    {"topic": {"name": "llm"}},
                                ]
                            },
                            "createdAt": "2024-01-01T00:00:00Z",
                            "updatedAt": "2024-06-01T00:00:00Z",
                        },
                        {
                            "nameWithOwner": "org/ml-toolkit",
                            "name": "ml-toolkit",
                            "description": None,
                            "url": "https://github.com/org/ml-toolkit",
                            "stargazerCount": 300,
                            "primaryLanguage": None,
                            "repositoryTopics": {"nodes": []},
                            "createdAt": "2024-03-01T00:00:00Z",
                            "updatedAt": "2024-05-01T00:00:00Z",
                        },
                    ]
                }
            }
        }

    def test_init_with_token(self, collector):
        """测试带 token 初始化"""
        assert collector.token == "test-token"
        assert collector.headers["Authorization"] == "Bearer test-token"
        assert collector.headers["Content-Type"] == "application/json"

    def test_init_without_token(self, collector_no_token):
        """测试无 token 初始化"""
        assert collector_no_token.token is None
        assert "Authorization" not in collector_no_token.headers

    def test_init_from_env(self):
        """测试从环境变量读取 token"""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env-token"}):
            c = Collector()
            assert c.token == "env-token"
            assert c.headers["Authorization"] == "Bearer env-token"

    def test_format_repo(self, collector):
        """测试格式化 repo 数据"""
        repo = {
            "nameWithOwner": "user/project",
            "name": "project",
            "description": "A test project",
            "url": "https://github.com/user/project",
            "stargazerCount": 100,
            "primaryLanguage": {"name": "Python"},
            "repositoryTopics": {
                "nodes": [{"topic": {"name": "ai"}}, {"topic": {"name": "ml"}}]
            },
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-06-01T00:00:00Z",
        }

        result = collector.format_repo(repo)

        assert result["id"] == "user/project"
        assert result["title"] == "project"
        assert result["description"] == "A test project"
        assert result["url"] == "https://github.com/user/project"
        assert result["stars"] == 100
        assert result["language"] == "Python"
        assert result["topics"] == ["ai", "ml"]
        assert result["created_at"] == "2024-01-01T00:00:00Z"
        assert result["updated_at"] == "2024-06-01T00:00:00Z"

    def test_format_repo_null_fields(self, collector):
        """测试格式化 repo 时处理 null 字段"""
        repo = {
            "nameWithOwner": "user/project",
            "name": "project",
            "description": None,
            "url": "https://github.com/user/project",
            "stargazerCount": 0,
            "primaryLanguage": None,
            "repositoryTopics": {"nodes": []},
            "createdAt": None,
            "updatedAt": None,
        }

        result = collector.format_repo(repo)

        assert result["description"] == ""
        assert result["language"] is None
        assert result["topics"] == []

    def test_fetch_trending(self, collector, sample_graphql_response):
        """测试 fetch_trending 正常流程"""
        with patch.object(collector, "_graphql_request") as mock_req:
            mock_req.return_value = sample_graphql_response

            repos = collector.fetch_trending(count=10)

            assert len(repos) == 2
            assert repos[0]["id"] == "user/ai-project"
            assert repos[0]["stars"] == 1500
            assert repos[1]["id"] == "org/ml-toolkit"
            assert repos[1]["description"] == ""

    def test_graphql_request_success(self, collector):
        """测试 GraphQL 请求成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"search": {"nodes": []}}}

        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.return_value = mock_response

            result = collector._graphql_request("query {}", {})

            assert result == {"data": {"search": {"nodes": []}}}
            mock_post.assert_called_once()

    def test_graphql_request_rate_limit(self, collector):
        """测试 rate limit 错误"""
        mock_response = Mock()
        mock_response.status_code = 403

        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(RuntimeError, match="rate limit"):
                collector._graphql_request("query {}", {})

    def test_graphql_request_server_error(self, collector):
        """测试服务器错误"""
        mock_response = Mock()
        mock_response.status_code = 500

        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(RuntimeError, match="GitHub API error: 500"):
                collector._graphql_request("query {}", {})

    def test_graphql_request_graphql_error(self, collector):
        """测试 GraphQL 错误响应"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errors": [{"message": "bad query"}]}

        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(RuntimeError, match="GraphQL error"):
                collector._graphql_request("query {}", {})

    def test_graphql_request_retry_on_network_error(self, collector):
        """测试网络错误重试"""
        import requests as req

        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {"data": {}}

        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.side_effect = [
                req.exceptions.ConnectionError("connection refused"),
                mock_success,
            ]

            with patch("pipeline.collector.time.sleep"):
                result = collector._graphql_request("query {}", {})

            assert result == {"data": {}}
            assert mock_post.call_count == 2

    def test_graphql_request_all_retries_fail(self, collector):
        """测试所有重试都失败"""
        import requests as req

        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.side_effect = req.exceptions.ConnectionError("connection refused")

            with patch("pipeline.collector.time.sleep"):
                with pytest.raises(RuntimeError, match="failed after 3 attempts"):
                    collector._graphql_request("query {}", {})

            assert mock_post.call_count == 3

    def test_append_to_raw_new_file(self, collector, tmp_path):
        """测试写入新 raw 文件"""
        with patch("pipeline.collector.Path") as mock_path_cls:
            raw_dir = tmp_path / "knowledge" / "raw"
            raw_dir.mkdir(parents=True)
            mock_path_cls.return_value = raw_dir

            # Use real Path for the actual file operations
            items = [
                {"id": "user/project", "title": "project", "stars": 100},
            ]

            # Directly test with real paths
            raw_file = raw_dir / "github-trending-2024-01-01.json"

            with patch("pipeline.collector.Path") as mock_path:
                mock_path.return_value = raw_dir
                # Just call the method with a patched path
                collector.append_to_raw.__func__

        # Simpler approach: test with monkeypatch
        items = [{"id": "user/project", "title": "project", "stars": 100}]
        raw_dir = tmp_path / "knowledge" / "raw"
        raw_dir.mkdir(parents=True)

        with patch("pipeline.collector.Path", return_value=raw_dir):
            result = collector.append_to_raw(items, date="2024-01-01")

        raw_file = raw_dir / "github-trending-2024-01-01.json"
        assert raw_file.exists()

        with open(raw_file, "r") as f:
            data = json.load(f)

        assert data["source"] == "github-trending"
        assert data["count"] == 1
        assert data["items"][0]["id"] == "user/project"
        assert data["query"] == QUERY

    def test_append_to_raw_deduplication(self, collector, tmp_path):
        """测试追加时去重"""
        raw_dir = tmp_path / "knowledge" / "raw"
        raw_dir.mkdir(parents=True)

        existing_data = {
            "source": "github-trending",
            "collected_at": "2024-01-01T00:00:00Z",
            "query": QUERY,
            "count": 1,
            "items": [{"id": "user/existing", "title": "existing"}],
        }

        raw_file = raw_dir / "github-trending-2024-01-01.json"
        with open(raw_file, "w") as f:
            json.dump(existing_data, f)

        new_items = [
            {"id": "user/existing", "title": "existing"},  # duplicate
            {"id": "user/new-project", "title": "new"},  # new
        ]

        with patch("pipeline.collector.Path", return_value=raw_dir):
            collector.append_to_raw(new_items, date="2024-01-01")

        with open(raw_file, "r") as f:
            data = json.load(f)

        assert data["count"] == 2
        ids = [item["id"] for item in data["items"]]
        assert "user/existing" in ids
        assert "user/new-project" in ids

    def test_collect_full_flow(self, collector):
        """测试完整采集流程"""
        mock_repos = [
            {"id": "user/project", "title": "project", "stars": 100},
        ]

        with patch.object(collector, "fetch_trending", return_value=mock_repos):
            with patch.object(collector, "append_to_raw", return_value="knowledge/raw/github-trending-2024-01-01.json"):
                with patch("pipeline.collector.time.sleep"):
                    result = collector.collect(count=10, date="2024-01-01")

        assert result == "knowledge/raw/github-trending-2024-01-01.json"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
