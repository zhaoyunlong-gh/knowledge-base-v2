"""Article 整理器 - 将分析结果转换为 article 并维护索引"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


class Organizer:
    """将分析结果整理成 article 的整理器"""

    def __init__(self):
        self.articles_dir = Path("knowledge/articles")
        self.articles_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.articles_dir / "index.json"

    def generate_slug(self, item: dict) -> str:
        """从 item 生成 slug

        Args:
            item: raw 文件中的 item

        Returns:
            slug 字符串，如 "fast-graphrag-better-rag" 或 "openai-agents-sdk"
        """
        item_id = item.get("id", "")

        # HN items: 从标题生成 slug
        if item_id.startswith("hn-"):
            title = item.get("title", "")
            # 移除 "Show HN: " / "Ask HN: " / "Launch HN: " 前缀
            title = title.replace("Show HN: ", "").replace("Ask HN: ", "").replace("Launch HN: ", "")
            # 转小写，只保留字母数字和空格
            slug = re.sub(r'[^a-zA-Z0-9\s]', '', title.lower())
            # 用横线替换空格，并截断
            slug = "-".join(slug.split())[:50]
            return slug if slug else item_id

        # GitHub items: 从 repo id 生成 slug
        return item_id.replace("/", "-")

    def generate_id(self, date: str, seq: int) -> str:
        """生成 article id

        Args:
            date: 日期字符串，如 "2026-03-17"
            seq: 序号

        Returns:
            id 字符串，如 "kb-2026-03-17-001"
        """
        return f"kb-{date}-{seq:03d}"

    def create_article(self, item: dict, date: str, seq: int) -> dict:
        """从 raw item 生成 article

        Args:
            item: raw 文件中的 item
            date: 日期字符串
            seq: 序号

        Returns:
            article 字典
        """
        item_id = item.get("id", "")
        if not item_id:
            raise ValueError(f"Item missing required 'id' field: {item}")

        slug = self.generate_slug(item)

        # 根据 signal_type 或 id 前缀确定 source
        signal_type = item.get("signal_type", "")
        if signal_type == "hacker-news" or item_id.startswith("hn-"):
            source = "hacker-news"
        else:
            source = "github-trending"

        article = {
            "id": self.generate_id(date, seq),
            "title": item.get("title", item_id.split("/")[-1]),
            "source": source,
            "source_id": item_id,
            "url": item.get("url", ""),
            "summary": item.get("summary", ""),
            "tags": item.get("tags", []),
            "relevance_score": item.get("relevance_score", 0.0),
            "collected_at": item.get("created_at"),
            "analyzed_at": item.get("analyzed_at"),
            "organized_at": datetime.utcnow().isoformat() + "Z",
            "status": "published",
        }

        return article

    def save_article(self, article: dict, slug: str, date: str) -> str:
        """保存 article 到文件

        Args:
            article: article 字典
            slug: slug 字符串
            date: 日期字符串

        Returns:
            文件路径
        """
        filename = f"{date}-{slug}.json"
        filepath = self.articles_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)

        return str(filepath)

    def load_index(self) -> dict:
        """加载 index.json，如果不存在则返回空结构"""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"updated_at": None, "count": 0, "articles": []}

    def save_index(self, index: dict) -> None:
        """保存 index.json"""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def organize_all(self, raw_file: str) -> int:
        """处理 raw 文件中所有已分析的 items

        Args:
            raw_file: raw 文件路径

        Returns:
            处理的 article 数量
        """
        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])
        date = datetime.now().strftime("%Y-%m-%d")

        # 加载 index 一次，避免重复 I/O
        index = self.load_index()
        existing_slugs = {article["slug"] for article in index.get("articles", [])}
        start_seq = index.get("count", 0) + 1

        article_count = 0

        for i, item in enumerate(items):
            # 只处理有 analyzed_at 字段的 item
            if not item.get("analyzed_at"):
                continue

            # 跳过缺少 id 的 item
            if not item.get("id"):
                print(f"[Organizer] Skipping item at index {i}: missing 'id' field")
                continue

            slug = self.generate_slug(item)

            # 检查是否重复（使用内存中的 set，避免重复加载 index）
            if slug in existing_slugs:
                print(f"[Organizer] Skipping duplicate: {slug}")
                continue

            seq = start_seq + article_count
            article = self.create_article(item, date, seq)

            filepath = self.save_article(article, slug, date)
            print(f"[Organizer] Created {filepath}")

            # 更新内存中的 index，批量写入
            index["articles"].append({
                "id": article["id"],
                "slug": slug,
                "path": f"{date}-{slug}.json",
            })
            existing_slugs.add(slug)
            article_count += 1

        # 一次性更新并保存 index
        if article_count > 0:
            index["updated_at"] = datetime.utcnow().isoformat() + "Z"
            index["count"] = len(index["articles"])
            self.save_index(index)

        return article_count

    def organize(self, raw_file: str) -> int:
        """执行整理流程

        Args:
            raw_file: raw 文件路径

        Returns:
            处理的 article 数量
        """
        print(f"[Organizer] Starting organization of {raw_file}...")

        count = self.organize_all(raw_file)

        print(f"[Organizer] Completed. Created {count} articles.")

        return count
