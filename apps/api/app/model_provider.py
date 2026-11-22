from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .config import Settings
from .http_client import proxy_url_from_env


class ModelProviderError(RuntimeError):
    pass


class ModelProvider(ABC):
    @abstractmethod
    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        purpose: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        purpose: str,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def test_connection(self) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(ModelProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_model:
            raise ModelProviderError(
                "未配置模型。请设置 LLM_MODEL（或 LLM_MODEL_ID）和 LLM_BASE_URL。"
            )
        self.settings = settings
        base_url = settings.llm_base_url.rstrip("/")
        self.endpoint = (
            base_url
            if base_url.endswith("/chat/completions")
            else f"{base_url}/chat/completions"
        )

    async def _post_json(
        self,
        *,
        body: dict[str, Any],
        purpose: str,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.llm_timeout_seconds,
                follow_redirects=True,
                proxy=proxy_url_from_env(),
                trust_env=False,
            ) as client:
                response = await client.post(self.endpoint, headers=headers, json=body)
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise ModelProviderError(
                _format_http_error(error.response)
            ) from error
        except httpx.TimeoutException as error:
            detail = str(error).strip() or error.__class__.__name__
            raise ModelProviderError(
                "模型接口请求超时"
                f"（{self.settings.llm_timeout_seconds:g} 秒）：{detail}"
            ) from error
        except httpx.HTTPError as error:
            detail = str(error).strip() or error.__class__.__name__
            raise ModelProviderError(f"模型接口请求失败：{detail}") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise ModelProviderError(
                f"模型接口未返回 JSON（{purpose}）。"
            ) from error
        if not isinstance(payload, dict):
            raise ModelProviderError(f"模型接口响应格式异常（{purpose}）。")
        return payload

    @staticmethod
    def _extract_content(payload: dict[str, Any], purpose: str) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelProviderError(
                f"模型响应格式异常（{purpose}），未找到 choices[0].message.content。"
            ) from error

        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content)

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        purpose: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": self.settings.llm_max_output_tokens,
        }
        if self.settings.llm_json_mode:
            body["response_format"] = {"type": "json_object"}

        payload = await self._post_json(body=body, purpose=purpose)
        content = self._extract_content(payload, purpose)
        return parse_json_content(content, purpose)

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        purpose: str,
    ) -> str:
        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": self.settings.llm_max_output_tokens,
        }
        payload = await self._post_json(body=body, purpose=purpose)
        return self._extract_content(payload, purpose).strip()

    async def test_connection(self) -> str:
        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {
                    "role": "user",
                    "content": 'Return exactly this JSON object: {"ok": true}',
                }
            ],
            "temperature": 0,
            "max_tokens": min(self.settings.llm_max_output_tokens, 32),
        }
        if self.settings.llm_json_mode:
            body["response_format"] = {"type": "json_object"}

        payload = await self._post_json(body=body, purpose="connection test")
        content = self._extract_content(payload, "connection test")
        parsed = parse_json_content(content, "connection test")
        if parsed.get("ok") is not True:
            raise ModelProviderError(
                "模型接口已响应，但连接测试返回了非预期结果。"
            )
        return "模型接口连接正常。"


class MockProvider(ModelProvider):
    """Deterministic offline provider used by tests and UI development."""

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        purpose: str,
    ) -> dict[str, Any]:
        del system_prompt
        if purpose == "classification":
            return {
                "canonical_title": "Imported Paper: Safety Evaluation Pipeline",
                "title_zh": "导入论文：安全评估流水线",
                "authors": ["Paper Atlas Import"],
                "venue": "Local test",
                "year": 2026,
                "abstract": "A deterministic mock paper used to validate the URL import pipeline.",
                "language": "en",
                "keywords": ["LLM safety", "evaluation"],
                "primary_category_id": "cat-05",
                "primary_category_name": "评测基准与工具",
                "confidence": 0.88,
                "rationale": "The mock text emphasizes evaluation and measurement.",
                "candidate_categories": [
                    {
                        "category_id": "cat-05",
                        "category_name": "评测基准与工具",
                        "confidence": 0.88,
                        "rationale": "Primary match.",
                    },
                    {
                        "category_id": "cat-01",
                        "category_name": "微调安全：机理与测量",
                        "confidence": 0.42,
                        "rationale": "Secondary safety measurement match.",
                    },
                ],
                "needs_review": False,
            }

        if purpose == "analysis":
            return {
                "problem": "如何把论文导入、分类和结构化解读串成可追踪流程。",
                "method": "下载 PDF 后提取页级文本，调用模型完成分类，再生成带证据页码的双语解读。",
                "findings": [
                    "任务进度可以在前端持续轮询",
                    "文件在分类完成后进入正式知识库目录",
                ],
                "innovations": [
                    {
                        "claim": "把论文导入和知识库分析连接为单一步骤。",
                        "evidence_pages": [1],
                        "evidence_quotes": [
                            "The imported paper is processed and indexed in one pipeline."
                        ],
                    }
                ],
                "limitations": ["Mock provider 只用于离线验证，不代表真实模型解读质量。"],
                "thesis_zh": "该实验验证链接导入、自动分类、知识库写入和前端加载的完整闭环。",
                "novelty_zh": "把收件箱、模型分类、结构化解读和 Markdown 索引整合为一条自动流水线。",
                "thesis_en": "The experiment verifies the complete loop from URL import and classification to knowledge-base export and frontend loading.",
                "novelty_en": "It combines inbox staging, model classification, structured interpretation and Markdown indexing into one automated pipeline.",
                "relation_to_library": "属于知识库基础设施，为后续论文导入和评测提供入口。",
                "confidence": 0.81,
                "needs_review": True,
            }

        raise ModelProviderError(f"Mock provider 不支持任务类型：{purpose}")

    async def test_connection(self) -> str:
        return "Mock provider 可用。"

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        purpose: str,
    ) -> str:
        del system_prompt
        if purpose != "translation":
            raise ModelProviderError(f"Mock provider 不支持任务类型：{purpose}")
        page_match = re.search(r"\[PAGE (\d+)\]", user_prompt)
        page_label = page_match.group(1) if page_match else "1"
        return (
            f"这是论文第 {page_label} 页的离线中文译文。"
            "该结果由 MockProvider 生成，用于验证翻译、页面展示和下载链路。"
        )


def _format_http_error(response: httpx.Response) -> str:
    code = ""
    message = ""
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or "")
            message = str(error.get("message") or "")
        code = str(payload.get("code") or code)
        message = str(payload.get("message") or message)

    detail = ": ".join(part for part in (code, message) if part)
    if not detail:
        detail = response.text.strip()[:400] or response.reason_phrase
    return f"模型接口返回 {response.status_code}: {detail[:800]}"


def parse_json_content(content: str, purpose: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ModelProviderError(f"模型未返回有效 JSON（{purpose}）。")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise ModelProviderError(f"模型 JSON 解析失败（{purpose}）：{error}") from error

    if not isinstance(parsed, dict):
        raise ModelProviderError(f"模型输出必须是 JSON 对象（{purpose}）。")
    return parsed


def build_provider(settings: Settings) -> ModelProvider:
    if settings.llm_provider.lower() == "mock":
        return MockProvider()
    if not settings.model_configured:
        raise ModelProviderError(
            "模型未配置。请在 apps/api/.env 中设置 LLM_BASE_URL、LLM_MODEL 和 LLM_API_KEY。"
        )
    return OpenAICompatibleProvider(settings)
