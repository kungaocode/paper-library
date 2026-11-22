from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .config import ResearchSettings


class ProviderError(RuntimeError):
    pass


PURPOSES = (
    "deep_analysis",
    "ideation",
    "critique",
    "direction",
    "experiment",
)


def _proxy_url() -> str | None:
    import os

    for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        value = os.getenv(name)
        if value and not value.startswith("socks"):
            return value
    return None


class ResearchProvider(ABC):
    @abstractmethod
    async def generate_json(
        self, *, system_prompt: str, user_prompt: str, purpose: str
    ) -> dict[str, Any]:
        raise NotImplementedError


class OpenAICompatibleProvider(ResearchProvider):
    """Strong-model backend. Never used until RESEARCH_LLM_* is filled in."""

    def __init__(self, settings: ResearchSettings) -> None:
        if not settings.llm_model:
            raise ProviderError(
                "未配置研究模型。请在 apps/research-api/.env 设置 "
                "RESEARCH_LLM_MODEL、RESEARCH_LLM_BASE_URL 和 RESEARCH_LLM_API_KEY。"
            )
        self.settings = settings
        base_url = settings.llm_base_url.rstrip("/")
        self.endpoint = (
            base_url
            if base_url.endswith("/chat/completions")
            else f"{base_url}/chat/completions"
        )

    async def generate_json(
        self, *, system_prompt: str, user_prompt: str, purpose: str
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4 if purpose in {"ideation", "direction"} else 0.1,
            "max_tokens": self.settings.llm_max_output_tokens,
        }
        if self.settings.llm_json_mode:
            body["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.llm_timeout_seconds,
                proxy=_proxy_url(),
                trust_env=False,
            ) as client:
                response = await client.post(self.endpoint, headers=headers, json=body)
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise ProviderError(_format_http_error(error.response)) from error
        except httpx.TimeoutException as error:
            raise ProviderError(
                f"模型接口请求超时（{self.settings.llm_timeout_seconds:g} 秒）：{error}"
            ) from error
        except httpx.HTTPError as error:
            raise ProviderError(f"模型接口请求失败：{error}") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderError(f"模型接口未返回 JSON（{purpose}）。") from error

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderError(
                f"模型响应格式异常（{purpose}），未找到 choices[0].message.content。"
            ) from error
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return parse_json_content(str(content), purpose)


PAPER_ID_RE = re.compile(r"paper-[0-9a-f]{8,}")
# Evidence cards print "chunk_id=<id>" verbatim, so the mock can quote real
# chunk ids back and the citation validator sees genuine evidence_refs.
CHUNK_ID_RE = re.compile(r"chunk_id=([^\s|]+)")


class MockResearchProvider(ResearchProvider):
    """Deterministic offline provider.

    It reads the real paper ids out of the prompt so that downstream citation
    validation is genuinely exercised (a fake id would be rejected, as it should).
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate_json(
        self, *, system_prompt: str, user_prompt: str, purpose: str
    ) -> dict[str, Any]:
        del system_prompt
        self.calls.append(purpose)
        ids = list(dict.fromkeys(PAPER_ID_RE.findall(user_prompt)))
        chunk_ids = list(dict.fromkeys(CHUNK_ID_RE.findall(user_prompt)))[:4]

        if purpose == "deep_analysis":
            page_count = _extract_int(user_prompt, r"页数：(\d+)") or 12
            page = max(1, min(page_count, 3))
            title = _extract_text(user_prompt, r"论文标题：(.+)") or "该论文"
            return {
                "problem": f"{title} 试图解决的核心问题（离线 mock 提取）。",
                "method": "从 PDF 正文中提取方法与实验设置（离线 mock）。",
                "findings": [
                    "主要发现一：方法在给定基准上有效（mock）",
                    "主要发现二：存在明确的适用边界（mock）",
                ],
                "innovations": [
                    {
                        "claim": "把已有组件重组成新的可验证流程（mock 创新点）",
                        "evidence_pages": [page],
                        "evidence_quotes": ["The proposed method integrates existing components."],
                    }
                ],
                "limitations": ["离线 mock 结果仅用于验证链路，不代表真实模型解读质量。"],
                "confidence": 0.6,
                "needs_review": True,
            }

        if purpose == "ideation":
            first = ids[0] if ids else "paper-unknown"
            second = ids[1] if len(ids) > 1 else first
            return {
                "ideas": [
                    {
                        "title": "把安全token约束迁移到智能体工具调用链（mock 想法）",
                        "hypothesis": "在工具调用决策点施加与 PACT 同构的置信度约束，"
                        "可在不牺牲任务成功率的情况下降低间接提示注入的成功率。",
                        "motivation": "微调安全证明安全能力集中在少量 token 上，"
                        "而智能体安全显示注入通过数据通道进入决策，两者都指向'决策点约束'。",
                        "method_sketch": "1) 用注入语料标注工具调用决策 token；"
                        "2) 在这些 token 上加参考模型锚定正则；3) 在 AgentHarm 类基准上评测 ASR 与任务成功率。",
                        "expected_contribution": "把训练期安全约束从模型权重扩展到智能体运行时决策点。",
                        "novelty_claim": "现有工作要么只约束权重（PACT/SAP），要么只做运行时检测（SmoothLLM），"
                        "本想法把两者合到同一个 token 级目标上。",
                        "risks": ["决策 token 的界定可能不稳定", "约束过强会损害工具选择能力"],
                        "required_resources": ["开源 7B 级对话模型", "提示注入基准", "单卡微调环境"],
                        "source_paper_ids": [first, second],
                        "evidence_refs": chunk_ids,
                        "confidence": 0.62,
                    },
                    {
                        "title": "用损失景观几何预测越狱迁移性（mock 想法）",
                        "hypothesis": "扰动是否跨出安全盆地，可预测对抗后缀在模型族之间的迁移成功率。",
                        "motivation": "VISAGE 类度量把安全退化几何化，而 GCG 类攻击依赖跨模型迁移，"
                        "两者的共同变量是权重空间距离。",
                        "method_sketch": "对多个开源模型计算盆地边界，测量 GCG 后缀迁移率，拟合两者的相关性。",
                        "expected_contribution": "给出'攻击何时会扩散'的可计算判据，服务于防御优先级排序。",
                        "novelty_claim": "把迁移性从经验现象变成损失景观上的几何预测问题。",
                        "risks": ["盆地边界估计成本高", "相关性可能被训练数据重叠混淆"],
                        "required_resources": ["多模型权重访问", "GPU 集群时间"],
                        "source_paper_ids": ids[:3] or [first],
                        "evidence_refs": chunk_ids,
                        "confidence": 0.55,
                    },
                ]
            }

        if purpose == "critique":
            return {
                "novelty": 0.72,
                "feasibility": 0.61,
                "evidence_support": 0.68,
                "risk": 0.45,
                "verdict": "值得小规模验证：假设可证伪，且引用了语料内真实论文。",
                "unsupported_claims": ["'显著降低'需要给出具体指标与基线后才能成立"],
                "suggested_fix": "先在单一开源模型上做概念验证，再扩展到多模型族。",
            }

        if purpose == "direction":
            return {
                "directions": [
                    {
                        "name": "决策点安全约束：从权重到运行时（mock 方向）",
                        "question": "能否用统一的 token 级约束同时覆盖微调期与智能体运行时的安全退化？",
                        "rationale": "语料中微调安全（cat-01/02）与智能体安全（cat-04）分别给出"
                        "'少量关键 token'与'决策点被数据污染'两条证据，合并后指向同一干预层。",
                        "gap_analysis": "缺少把训练期约束与运行时决策点对齐的公开工作，"
                        "也缺少同时报告 ASR 与任务成功率的基准协议。",
                        "roadmap": [
                            "复现 PACT 基线并确认安全 token 集合",
                            "构造工具调用决策 token 标注流程",
                            "在注入基准上联合评测 ASR 与任务成功率",
                            "扩展到多轮智能体与多模型族",
                        ],
                        "success_metrics": [
                            "ASR 相对基线下降且任务成功率损失小于 2%",
                            "约束在不同注入模板下保持有效",
                        ],
                        "open_risks": ["决策 token 界定的可复现性", "计算预算"],
                        "member_idea_ids": _extract_ids(user_prompt, "idea-"),
                        "source_paper_ids": ids[:4],
                        "priority": 0.78,
                        "parent_direction_id": _extract_text(user_prompt, r"上一代方向ID：(\S+)") or "",
                    }
                ]
            }

        if purpose == "experiment":
            direction_name = _extract_text(user_prompt, r"研究方向：(.+)") or "该方向"
            return {
                "objective": f"验证 {direction_name} 的核心假设是否成立。",
                "hypothesis": "在决策点施加 token 级安全约束可降低注入成功率，且任务成功率损失可控。",
                "datasets": ["AgentHarm", "AdvBench", "自建工具调用注入集"],
                "baselines": ["无约束微调", "PACT", "SmoothLLM 运行时检测"],
                "metrics": ["ASR", "任务成功率", "安全token置信度漂移", "推理开销"],
                "protocol_steps": [
                    "固定随机种子，准备基座与对齐参考模型",
                    "标注决策 token 并生成约束正则项",
                    "分别训练基线与本方法，记录同一评测集结果",
                    "做消融：随机 token 约束 / 仅运行时检测 / 组合",
                ],
                "ablations": ["随机 token 对照", "去掉参考模型锚定", "约束强度扫描"],
                "compute_estimate": "单张 80G GPU 约 2-3 天（7B LoRA）",
                "falsification_criteria": "若 ASR 下降不足 10% 或任务成功率下降超过 5%，则假设被否证。",
                "timeline": ["第 1-2 周：基线复现", "第 3-5 周：方法实现", "第 6-7 周：评测与消融"],
                "risks": ["基准饱和导致区分度不足", "决策 token 标注不一致"],
                "followups": [
                    {
                        "kind": "paper_to_read",
                        "query": "agent decision token safety constraint fine-tuning",
                        "reason": "需要确认是否已有工作在运行时决策点上做训练期约束。",
                    },
                    {
                        "kind": "dataset",
                        "query": "indirect prompt injection benchmark with tool calls",
                        "reason": "现有注入基准多数不覆盖多轮工具调用。",
                    },
                    {
                        "kind": "tool",
                        "query": "activation annotation tool for decision tokens",
                        "reason": "决策 token 标注需要可复现的工具支持。",
                    },
                ],
            }

        raise ProviderError(f"Mock provider 不支持任务类型：{purpose}")


def _extract_text(prompt: str, pattern: str) -> str:
    match = re.search(pattern, prompt)
    return match.group(1).strip() if match else ""


def _extract_int(prompt: str, pattern: str) -> int:
    text = _extract_text(prompt, pattern)
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 0


def _extract_ids(prompt: str, prefix: str) -> list[str]:
    return list(dict.fromkeys(re.findall(rf"{prefix}[0-9a-f]{{8,}}", prompt)))


def _format_http_error(response: httpx.Response) -> str:
    detail = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                detail = str(error.get("message") or "")
            detail = detail or str(payload.get("message") or "")
    except ValueError:
        detail = ""
    if not detail:
        detail = response.text.strip()[:300] or response.reason_phrase
    return f"模型接口返回 {response.status_code}: {detail[:600]}"


def parse_json_content(content: str, purpose: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ProviderError(f"模型未返回有效 JSON（{purpose}）。")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise ProviderError(f"模型 JSON 解析失败（{purpose}）：{error}") from error
    if not isinstance(parsed, dict):
        raise ProviderError(f"模型输出必须是 JSON 对象（{purpose}）。")
    return parsed


def build_provider(settings: ResearchSettings) -> ResearchProvider:
    if settings.llm_provider.lower() == "mock":
        return MockResearchProvider()
    if not settings.model_configured:
        raise ProviderError(
            "研究模型未配置。请在 apps/research-api/.env 填写 RESEARCH_LLM_BASE_URL、"
            "RESEARCH_LLM_MODEL 和 RESEARCH_LLM_API_KEY，或设 RESEARCH_LLM_PROVIDER=mock。"
        )
    return OpenAICompatibleProvider(settings)
