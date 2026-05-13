## ADDED Requirements

### Requirement: HN Data Collection
The system SHALL collect Hacker News articles via Algolia HN API with configurable keywords and batch size.

#### Scenario: Successful HN API fetch
- **WHEN** system executes HN data collection task
- **THEN** system SHALL fetch up to 50 articles from Algolia HN API
- **AND** system SHALL use query parameter `"AI OR LLM OR agent OR machine-learning"`
- **AND** system SHALL use tags parameter `"story"`

#### Scenario: Rate limit handling
- **WHEN** HN API returns rate limit error (429)
- **THEN** system SHALL wait 1 second and retry
- **AND** system SHALL retry up to 3 times maximum

#### Scenario: Network error handling
- **WHEN** HN API returns network error
- **THEN** system SHALL log the error with timestamp
- **AND** system SHALL NOT block GitHub Trending collection task

### Requirement: Keyword Filtering
The system SHALL filter HN articles using keyword whitelist to retain only AI-related content.

#### Scenario: Filter by keyword match
- **WHEN** HN articles are fetched
- **THEN** system SHALL retain only articles where title contains any of: `LLM`, `RAG`, `fine-tuning`, `agent`, `MCP` (case-insensitive)

#### Scenario: No keyword match
- **WHEN** HN article title does not contain any whitelisted keyword
- **THEN** system SHALL exclude that article from results

### Requirement: Data Formatting
The system SHALL format HN articles into standard data model with signal_type field.

#### Scenario: Format HN article data
- **WHEN** HN articles are collected
- **THEN** system SHALL add field `signal_type = "hacker-news"` to each item
- **AND** system SHALL add field `id` with format `hn-{article_id}`
- **AND** system SHALL convert `created_at_i` to ISO datetime format as `created_at`

### Requirement: Raw Data Storage
The system SHALL store HN articles to `knowledge/raw/hacker-news-{date}.json` with append behavior.

#### Scenario: Create new raw file
- **WHEN** no raw file exists for date
- **THEN** system SHALL create new file with structure: `{source, collected_at, query, count, items}`

#### Scenario: Append to existing raw file
- **WHEN** raw file already exists for date
- **THEN** system SHALL append new items to existing items array
- **AND** system SHALL update `count` to reflect total items
- **AND** system SHALL update `collected_at` timestamp

#### Scenario: Deduplication by URL
- **WHEN** appending items to raw file
- **THEN** system SHALL skip items where `url` already exists in existing items

### Requirement: Configuration Management
The system SHALL read HN data source parameters from `rss_sources.yaml` configuration file.

#### Scenario: Load HN configuration
- **WHEN** HN collector initializes
- **THEN** system SHALL read `hacker_news` section from `rss_sources.yaml`
- **AND** system SHALL use `api_url`, `keywords`, and `batch_size` from config

### Requirement: Error Logging
The system SHALL log HN collection task status for observability.

#### Scenario: Log task start
- **WHEN** HN collection task begins
- **THEN** system SHALL log `"[HackerNewsCollector] Starting HN data collection..."`

#### Scenario: Log task completion
- **WHEN** HN collection task completes successfully
- **THEN** system SHALL log `"[HackerNewsCollector] Collected {count} items, saved to {file_path}"`

#### Scenario: Log task failure
- **WHEN** HN collection task fails after all retries
- **THEN** system SHALL log `"[HackerNewsCollector] Collection failed: {error_message}"`