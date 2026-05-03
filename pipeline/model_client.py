"""统一的 LLM 客户端，支持 OpenAI 兼容 API（DeepSeek / Qwen / OpenAI）"""
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class ModelConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout: int = 30


class ModelClient:
    """统一的 LLM 客户端"""

    def __init__(self, config: Optional[ModelConfig] = None):
        if config is None:
            config = self.load_config()
        self.config = config

    @staticmethod
    def load_config() -> ModelConfig:
        """从环境变量或 .env 文件加载配置"""
        from dotenv import load_dotenv

        load_dotenv()

        api_key = os.environ.get("LLM_API_KEY")
        base_url = os.environ.get("LLM_BASE_URL")
        model = os.environ.get("LLM_MODEL")

        if not api_key:
            raise ValueError("LLM_API_KEY is required")

        return ModelConfig(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1/chat/completions",
            model=model or "gpt-4o-mini",
        )

    def analyze(self, repo_info: dict) -> dict:
        """调用 LLM 分析单个 repo，返回结构化洞见

        Args:
            repo_info: 包含 name, description, stars, topics 等字段的 dict

        Returns:
            包含 summary, relevance_score, score_breakdown, tags, analyzed_at 的 dict
        """
        prompt = self._build_prompt(repo_info)
        response = self._call_llm(prompt)
        return self._parse_response(response)

    def _build_prompt(self, repo_info: dict) -> str:
        """构建分析 prompt"""
        name = repo_info.get("name", "")
        description = repo_info.get("description", "")
        stars = repo_info.get("stars", 0)
        topics = repo_info.get("topics", [])

        return f'''Return JSON for GitHub project analysis:

Project: {name}
Description: {description}
Stars: {stars}
Topics: {topics}

Respond with this exact JSON structure (replace values only):
{{"summary":"project summary in English","relevance_score":0.5,"score_breakdown":{{"tech_depth":5.0,"practical_value":5.0,"timeliness":5.0,"community_heat":5.0,"domain_match":5.0}},"tags":["tag1","tag2"]}}'''

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API，实现重试逻辑"""
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = self._make_request(prompt)
                return response
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"LLM API failed after {max_retries} attempts: {e}")
                time.sleep(retry_delay)

    def _make_request(self, prompt: str) -> str:
        """发送 HTTP 请求到 LLM API"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "Return ONLY valid JSON starting with {. No explanations, no markdown formatting."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,  # More deterministic output
            "max_tokens": self.config.max_tokens,
        }

        response = requests.post(
            self.config.base_url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout,
        )

        if response.status_code == 401 or response.status_code == 403:
            raise RuntimeError(f"LLM API authentication failed: {response.status_code}")
        elif response.status_code >= 500:
            raise RuntimeError(f"LLM API server error: {response.status_code}")
        elif response.status_code != 200:
            raise RuntimeError(f"LLM API error: {response.status_code} - {response.text}")

        return response.json()["choices"][0]["message"]["content"]

    def _parse_response(self, response: str) -> dict:
        """解析 LLM 返回的 JSON 响应"""
        import re

        # 移除 <think>... 标签
        cleaned = re.sub(r"<think>.*?", "", response, flags=re.DOTALL).strip()

        # 移除中文注释（如 "0.0到1.0之间"、"0.0-1.0" 等）
        # 并修复缺失的逗号
        def fix_chinese_value(match):
            key = match.group(1)
            text = match.group(2)
            # 提取第一个数字
            num_match = re.search(r'[0-9.]+', text)
            if not num_match:
                return match.group(0)
            num = float(num_match.group())
            # 判断是否需要归一化
            if "relevance_score" in key.lower():
                num = num / 10.0 if num > 1.0 else num
            else:
                num = min(10.0, num)
            return f'"{key}":{num}'

        # 处理 "field":数字+非数字字符... 格式，同时修复缺失逗号
        cleaned = re.sub(r'"([^"]+)":\s*([0-9.]+(?:[a-zA-Z一-鿿到\s\-/\\].*?)?)([,}]|\})', fix_chinese_value, cleaned)

        # 修复缺失逗号: 在数值后直接跟引号时插入逗号
        # 例如: 0.9"score -> 0.9,"score
        cleaned = re.sub(r'([0-9])\s*"', r'\1,"', cleaned)

        # 找到第一个 "summary": 的位置
        summary_idx = cleaned.find('"summary":')
        if summary_idx == -1:
            print(f"[ModelClient] No summary found. Preview: {cleaned[:500]}...")
            raise ValueError(f"No summary field found in response")

        print(f"[ModelClient] Found summary at {summary_idx}, full cleaned preview: {cleaned[:1000]}...")

        # Find first { after the thinking content
        first_brace = cleaned.find('{', 300)  # Skip first 300 chars (thinking content)
        if first_brace == -1:
            print(f"[ModelClient] No opening brace found")
            raise ValueError(f"No JSON found in response")

        # Find the matching closing brace by counting depth
        depth = 0
        end_idx = len(cleaned)
        for i in range(first_brace, len(cleaned)):
            if cleaned[i] == '{':
                depth += 1
            elif cleaned[i] == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        candidate = cleaned[first_brace:end_idx]
        print(f"[ModelClient] Extracted candidate from {first_brace} to {end_idx}: {candidate[:300]}...")

        # Fix missing commas: after numeric value or }, there should be a comma before next key
        # Pattern: 5.0"tags" -> 5.0,"tags" and }" -> },"
        before_fix = candidate
        # Fix after numbers: digit followed by quote
        candidate = re.sub(r'([0-9])\s*"', r'\1,"', candidate)
        # Fix after closing brace: } followed by quote
        candidate = re.sub(r'}\s*"', r'},"', candidate)
        if candidate != before_fix:
            print(f"[ModelClient] Fixed missing commas")

        # Fix truncated JSON: if it ends mid-value or mid-array, complete it
        stripped = candidate.rstrip()
        # If it ends with a partial value (like "t instead of "tutorial"), add closing
        if len(stripped) > 10 and not stripped.endswith('}') and not stripped.endswith('"]'):
            # Try to find where the JSON should properly end
            # Add appropriate closing
            print(f"[ModelClient] JSON appears truncated, adding closing braces")
            # Complete the most common incomplete patterns
            if stripped.endswith('"'):
                candidate = stripped + '"]}'
            elif stripped.endswith(',">'):
                candidate = stripped + '"]}'
            else:
                candidate = stripped + '}' * 3
            print(f"[ModelClient] Fixed truncated JSON: {candidate[-50:]}...")

        # If truncation fix attempt failed, create minimal valid JSON as last resort
        try:
            result = json.loads(candidate)
        except json.JSONDecodeError:
            print(f"[ModelClient] JSON parse failed, attempting minimal fix...")
            # Try creating a minimal valid JSON with what we can extract
            summary_match = re.search(r'"summary":"([^"]*)"', candidate)
            score_match = re.search(r'"relevance_score":([0-9.]+)', candidate)
            # Match tags array - capture content between [" and ]
            tags_match = re.search(r'"tags":\["([^"\]]*(?:"[^"]*)*)"\]', candidate)

            if summary_match and score_match:
                summary = summary_match.group(1)
                score = float(score_match.group(1))
                if score > 1.0:
                    score = score / 10.0
                score = max(0.0, min(1.0, score))

                tags = ["machine-learning", "deep-learning"]
                if tags_match:
                    try:
                        tags_str = tags_match.group(1)
                        if tags_str and len(tags_str) > 0:
                            if ',' in tags_str:
                                tags = [t.strip() for t in tags_str.split(',') if t.strip()]
                            else:
                                extracted = re.findall(r'"([^"]*)"', tags_str)
                                if extracted:
                                    tags = [t.strip() for t in extracted if t.strip()]
                            if not tags:
                                tags = ["machine-learning", "deep-learning"]
                    except Exception as e:
                        print(f"[ModelClient] Error parsing tags: {e}")
                        tags = ["machine-learning", "deep-learning"]

                result = {
                    "summary": summary[:200] if summary else "GitHub repository",
                    "relevance_score": score,
                    "score_breakdown": {
                        "tech_depth": 5.0,
                        "practical_value": 5.0,
                        "timeliness": 5.0,
                        "community_heat": 5.0,
                        "domain_match": 5.0
                    },
                    "tags": tags[:5] if tags else ["machine-learning", "deep-learning"]
                }
                print(f"[ModelClient] Created minimal valid JSON from extracted values")

                # Validate and normalize before returning
                from datetime import datetime
                if isinstance(result.get("relevance_score"), (int, float)):
                    if result["relevance_score"] > 1.0:
                        result["relevance_score"] = result["relevance_score"] / 10.0
                    result["relevance_score"] = max(0.0, min(1.0, result["relevance_score"]))

                result["analyzed_at"] = datetime.utcnow().isoformat() + "Z"
                return result
            else:
                raise ValueError(f"No valid JSON found in response")