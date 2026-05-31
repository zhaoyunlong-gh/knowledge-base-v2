"""测试 Collector"""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from pipeline.collector import Collector


class TestCollector:
    """Collector 测试"""

    @pytest.fixture
    def sample_repo(self):
        """单个 repo 的 GraphQL 节点"""
        return {
            "nameWithOwner": "owner/awesome-llm",
            "name": "awesome-llm",
            "description": "An awesome LLM project",
            "url": "https://github.com/owner/awesome-llm",
            "stargazerCount": 1234,
            "primaryLanguage": {"name": "Python"},
            "repositoryTopics": {
                "nodes": [
                    {"topic": {"name": "llm"}},
                    {"topic": {"name": "ai"}},
                ]
            },
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-05-01T00:00:00Z",
        }

    @pytest.fixture
    def sample_graphql_response(self, sample_repo):
        """完整 GraphQL 响应"""
        return {"data": {"search": {"nodes": [sample_repo]}}}

    def test_init_with_token(self):
        """有 token 时设置 Authorization 头"""
        collector = Collector(token="abc123")
        assert collector.token == "abc123"
        assert collector.headers["Authorization"] == "Bearer abc123"
        assert collector.headers["Content-Type"] == "application/json"

    def test_init_without_token(self, monkeypatch):
        """无 token 时不发送 Authorization 头"""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        collector = Collector()
        assert collector.token is None
        assert "Authorization" not in collector.headers

    def test_init_token_from_env(self, monkeypatch):
        """从环境变量读取 token"""
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        collector = Collector()
        assert collector.token == "env-token"
        assert collector.headers["Authorization"] == "Bearer env-token"

    def test_format_repo(self, sample_repo):
        """格式化 repo 数据"""
        collector = Collector(token="x")
        formatted = collector.format_repo(sample_repo)

        assert formatted["id"] == "owner/awesome-llm"
        assert formatted["title"] == "awesome-llm"
        assert formatted["description"] == "An awesome LLM project"
        assert formatted["url"] == "https://github.com/owner/awesome-llm"
        assert formatted["stars"] == 1234
        assert formatted["language"] == "Python"
        assert formatted["topics"] == ["llm", "ai"]
        assert formatted["created_at"] == "2026-01-01T00:00:00Z"
        assert formatted["updated_at"] == "2026-05-01T00:00:00Z"

    def test_format_repo_null_fields(self):
        """处理 null 字段（description / primaryLanguage / topics）"""
        collector = Collector(token="x")
        repo = {
            "nameWithOwner": "owner/repo",
            "name": "repo",
            "description": None,
            "url": "https://github.com/owner/repo",
            "stargazerCount": 0,
            "primaryLanguage": None,
            "createdAt": None,
            "updatedAt": None,
        }
        formatted = collector.format_repo(repo)

        assert formatted["description"] == ""
        assert formatted["language"] is None
        assert formatted["topics"] == []
        assert formatted["created_at"] is None

    def test_fetch_trending(self, sample_graphql_response):
        """正常采集流程"""
        collector = Collector(token="x")
        with patch.object(
            collector, "_graphql_request", return_value=sample_graphql_response
        ) as mock_req:
            repos = collector.fetch_trending(count=10)

            mock_req.assert_called_once()
            assert len(repos) == 1
            assert repos[0]["id"] == "owner/awesome-llm"

    def test_graphql_request_success(self, sample_graphql_response):
        """GraphQL 请求成功返回"""
        collector = Collector(token="x")
        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200, json=lambda: sample_graphql_response
            )
            result = collector._graphql_request("query", {})
            assert result == sample_graphql_response

    def test_graphql_request_rate_limit(self):
        """403 触发 rate limit 错误"""
        collector = Collector(token="x")
        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=403, json=lambda: {})
            with pytest.raises(RuntimeError, match="rate limit"):
                collector._graphql_request("query", {})

    def test_graphql_request_non_200(self):
        """非 200/403 状态码抛错"""
        collector = Collector(token="x")
        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=500, json=lambda: {})
            with pytest.raises(RuntimeError, match="GitHub API error: 500"):
                collector._graphql_request("query", {})

    def test_graphql_request_graphql_error(self):
        """响应包含 errors 字段时抛错"""
        collector = Collector(token="x")
        with patch("pipeline.collector.requests.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200, json=lambda: {"errors": [{"message": "bad"}]}
            )
            with pytest.raises(RuntimeError, match="GraphQL error"):
                collector._graphql_request("query", {})

    def test_graphql_request_retry_then_success(self, sample_graphql_response):
        """网络异常重试后成功"""
        collector = Collector(token="x")
        responses = [
            requests.exceptions.ConnectionError("boom"),
            Mock(status_code=200, json=lambda: sample_graphql_response),
        ]
        with patch("pipeline.collector.requests.post", side_effect=responses) as mock_post, \
                patch("pipeline.collector.time.sleep"):
            result = collector._graphql_request("query", {})
            assert mock_post.call_count == 2
            assert result == sample_graphql_response

    def test_graphql_request_retry_exhausted(self):
        """连续网络异常耗尽重试后抛错"""
        collector = Collector(token="x")
        with patch(
            "pipeline.collector.requests.post",
            side_effect=requests.exceptions.ConnectionError("boom"),
        ) as mock_post, patch("pipeline.collector.time.sleep"):
            with pytest.raises(RuntimeError, match="failed after 3 attempts"):
                collector._graphql_request("query", {})
            assert mock_post.call_count == 3

    def test_append_to_raw_new_file(self, tmp_path, monkeypatch):
        """创建新的 raw 文件"""
        monkeypatch.chdir(tmp_path)
        collector = Collector(token="x")
        items = [{"id": "owner/repo", "title": "repo"}]

        raw_file = collector.append_to_raw(items, "2026-05-31")

        assert Path(raw_file).exists()
        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["source"] == "github-trending"
        assert data["count"] == 1
        assert len(data["items"]) == 1

    def test_append_to_raw_deduplication(self, tmp_path, monkeypatch):
        """重复 id 去重追加"""
        monkeypatch.chdir(tmp_path)
        collector = Collector(token="x")

        collector.append_to_raw([{"id": "owner/repo", "title": "first"}], "2026-05-31")
        raw_file = collector.append_to_raw(
            [
                {"id": "owner/repo", "title": "dup"},
                {"id": "owner/new", "title": "new"},
            ],
            "2026-05-31",
        )

        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["count"] == 2
        ids = {item["id"] for item in data["items"]}
        assert ids == {"owner/repo", "owner/new"}

    def test_collect(self, tmp_path, monkeypatch, sample_graphql_response):
        """完整采集流程"""
        monkeypatch.chdir(tmp_path)
        collector = Collector(token="x")
        with patch.object(
            collector, "_graphql_request", return_value=sample_graphql_response
        ), patch("pipeline.collector.time.sleep"):
            raw_file = collector.collect(count=5, date="2026-05-31")

        assert Path(raw_file).exists()
        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["count"] == 1
        assert data["items"][0]["id"] == "owner/awesome-llm"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
