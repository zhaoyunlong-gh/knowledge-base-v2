"""Pipeline CLI 入口 - 串联 Collector -> Analyzer -> Organizer"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


def validate_config() -> bool:
    """验证必需配置是否存在

    Returns:
        配置是否完整
    """
    required = ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"]
    missing = [k for k in required if not os.environ.get(k)]

    if missing:
        print(f"[Error] Missing required environment variables: {', '.join(missing)}")
        print("Please set them in .env file or environment.")
        return False

    return True


def run_pipeline(date: str = None, count: int = 50) -> int:
    """执行完整 pipeline

    Args:
        date: 日期字符串
        count: 采集数量

    Returns:
        0 成功，1 失败
    """
    from pipeline.collector import Collector
    from pipeline.analyzer import Analyzer
    from pipeline.organizer import Organizer

    print(f"[Pipeline] Starting at {datetime.now().isoformat()}")
    print(f"[Pipeline] Date: {date or 'today'}, Count: {count}")

    try:
        # Step 1: Collector - GitHub Trending
        print("\n=== Collector ===")
        collector = Collector()
        raw_file = collector.collect(count=count, date=date)
        print(f"[Collector] Raw file: {raw_file}")

        # Step 1b: Hacker News Collector
        print("\n=== HackerNews Collector ===")
        from pipeline.hacker_news_collector import HackerNewsCollector
        hn_collector = HackerNewsCollector()
        hn_raw_file = hn_collector.collect(count=count, date=date)
        if hn_raw_file:
            print(f"[HackerNewsCollector] Raw file: {hn_raw_file}")

        # Step 2: Analyzer
        print("\n=== Analyzer ===")
        analyzer = Analyzer()
        analyzed_count = analyzer.analyze(raw_file)
        print(f"[Analyzer] Analyzed {analyzed_count} repos from GitHub Trending")

        # Analyze Hacker News data
        if hn_raw_file:
            hn_analyzed_count = analyzer.analyze(hn_raw_file)
            print(f"[Analyzer] Analyzed {hn_analyzed_count} articles from Hacker News")

        # Step 3: Organizer
        print("\n=== Organizer ===")
        organizer = Organizer()
        article_count = organizer.organize(raw_file)
        print(f"[Organizer] Created {article_count} articles from GitHub Trending")

        # Organize Hacker News data
        if hn_raw_file:
            hn_article_count = organizer.organize(hn_raw_file)
            print(f"[Organizer] Created {hn_article_count} articles from Hacker News")

        print("\n[Pipeline] Completed successfully!")
        return 0

    except Exception as e:
        print(f"\n[Pipeline] Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


def main():
    parser = argparse.ArgumentParser(description="AI Knowledge Base Pipeline")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date for raw file (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of repos to fetch. Default: 10",
    )

    args = parser.parse_args()

    # 验证配置
    if not validate_config():
        sys.exit(1)

    # 运行 pipeline
    exit_code = run_pipeline(date=args.date, count=args.count)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()