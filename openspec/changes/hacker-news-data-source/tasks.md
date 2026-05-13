## 1. Setup

- [x] 1.1 Create `pipeline/hacker_news_collector.py` file
- [x] 1.2 Add HN configuration section to `pipeline/rss_sources.yaml`

## 2. Core Implementation

- [x] 2.1 Implement `HackerNewsCollector` class with `__init__`, `fetch`, `format`, `append_to_raw` methods
- [x] 2.2 Implement Algolia HN API call with rate limit handling (1s wait, 3 retries)
- [x] 2.3 Implement keyword whitelist filtering (`LLM`, `RAG`, `fine-tuning`, `agent`, `MCP`)
- [x] 2.4 Implement data formatting with `signal_type`, `id`, `created_at` fields
- [x] 2.5 Implement raw file storage with append and deduplication by URL

## 3. Integration

- [x] 3.1 Modify `pipeline/run.py` to call `HackerNewsCollector` in daily pipeline
- [x] 3.2 Add error logging for task start, completion, and failure

## 4. Testing

- [x] 4.1 Create `tests/pipeline/test_hacker_news_collector.py` with mock API responses
- [x] 4.2 Verify rate limit retry logic
- [x] 4.3 Verify keyword filtering logic
- [x] 4.4 Verify deduplication by URL