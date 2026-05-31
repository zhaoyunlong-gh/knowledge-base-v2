"""LLM 分析器 - 对 repo 进行 AI 分析"""
import json
import time
from datetime import datetime
from typing import Optional

from pipeline.model_client import ModelClient


class Analyzer:
    """使用 LLM 分析 GitHub repo 的分析器"""

    def __init__(self, model_client: Optional[ModelClient] = None):
        self.model_client = model_client or ModelClient()

    def analyze_repo(self, repo_info: dict) -> dict:
        """调用 LLM 分析单个 repo

        Args:
            repo_info: 包含 repo 信息的字典

        Returns:
            包含分析结果的字典，保证含 analyzed_at 字段
        """
        try:
            result = self.model_client.analyze(repo_info)
        except Exception as e:
            raise RuntimeError(f"Failed to analyze repo {repo_info.get('id', 'unknown')}: {e}")

        # 保证 analyzed_at 存在，否则增量分析（analyze_all 跳过逻辑）会失效
        if not result.get("analyzed_at"):
            result["analyzed_at"] = datetime.utcnow().isoformat() + "Z"
        return result

    def update_raw_with_insights(self, raw_file: str, repo_id: str, insights: dict) -> None:
        """将分析结果追加到 raw 文件中对应 item

        Args:
            raw_file: raw 文件路径
            repo_id: repo id
            insights: 分析结果
        """
        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("items", []):
            if item.get("id") == repo_id:
                item.update(insights)
                break

        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def analyze_all(self, raw_file: str) -> int:
        """批量处理 raw 文件中的所有 items

        Args:
            raw_file: raw 文件路径

        Returns:
            分析的 item 数量
        """
        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])
        analyzed_count = 0

        for i, item in enumerate(items):
            # 跳过已有 analyzed_at 的 item（增量分析）
            if item.get("analyzed_at"):
                continue

            item_id = item.get("id", "unknown")
            print(f"[Analyzer] Analyzing {i + 1}/{len(items)}: {item_id}")

            try:
                insights = self.analyze_repo(item)
                item.update(insights)  # 原地更新，循环结束后统一落盘
                analyzed_count += 1
            except Exception as e:
                print(f"[Analyzer] Error analyzing {item_id}: {e}")
                continue  # skip this repo, continue with next

            time.sleep(1)  # 请求间隔

        # 仅在有更新时写回一次，避免每条都全量读写 raw 文件
        if analyzed_count > 0:
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        return analyzed_count

    def analyze(self, raw_file: str) -> int:
        """执行分析流程

        Args:
            raw_file: raw 文件路径

        Returns:
            分析的 item 数量
        """
        print(f"[Analyzer] Starting analysis of {raw_file}...")

        count = self.analyze_all(raw_file)

        print(f"[Analyzer] Completed. Analyzed {count} repos.")

        return count
