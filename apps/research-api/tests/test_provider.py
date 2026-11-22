"""Provider layer: offline mock determinism, JSON parsing, config gating.

Nothing here touches the network. The OpenAI-compatible provider is only
constructed (never called): the user wires real credentials later.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.config import ResearchSettings
from app.provider import (
    MockResearchProvider,
    OpenAICompatibleProvider,
    ProviderError,
    _proxy_url,
    build_provider,
    parse_json_content,
)
from app.synthesis import FOLLOWUP_KINDS
from conftest import PAPERS

PAPER_A = PAPERS[0]["id"]
PAPER_B = PAPERS[1]["id"]

IDEATION_PROMPT = f"""【证据卡片】
[1] paper_id={PAPER_A} | chunk_id=chunk-aaa | 分类=cat-01
[2] paper_id={PAPER_B} | chunk_id=chunk-bbb | 分类=cat-04
"""

DIRECTION_PROMPT = f"""【本轮通过评审的想法】
- idea_id=idea-0123456789ab | 标题：想法一
- idea_id=idea-fedcba987654 | 标题：想法二
上一代方向ID：dir-0123456789ab
"""


async def test_mock_deep_analysis_stays_inside_the_page_range() -> None:
    provider = MockResearchProvider()

    payload = await provider.generate_json(
        system_prompt="sys",
        user_prompt="论文标题：细粒度对齐\n页数：7\n带页码的论文正文节选：\n[PAGE 1] ...",
        purpose="deep_analysis",
    )

    assert payload["problem"].startswith("细粒度对齐")
    assert payload["method"] and payload["findings"]
    innovation = payload["innovations"][0]
    assert innovation["claim"] and innovation["evidence_quotes"]
    # Page numbers must be usable as citations: 1 <= page <= page_count.
    assert all(1 <= page <= 7 for page in innovation["evidence_pages"])
    assert 0.0 <= payload["confidence"] <= 1.0
    assert payload["needs_review"] is True
    assert provider.calls == ["deep_analysis"]


async def test_mock_deep_analysis_has_safe_defaults_for_a_sparse_prompt() -> None:
    payload = await MockResearchProvider().generate_json(
        system_prompt="sys", user_prompt="", purpose="deep_analysis"
    )

    assert payload["problem"].startswith("该论文")
    assert payload["innovations"][0]["evidence_pages"] == [3]


async def test_mock_ideation_only_cites_ids_found_in_the_prompt() -> None:
    payload = await MockResearchProvider().generate_json(
        system_prompt="sys", user_prompt=IDEATION_PROMPT, purpose="ideation"
    )

    ideas = payload["ideas"]
    assert len(ideas) == 2
    for idea in ideas:
        assert idea["title"] and idea["hypothesis"] and idea["method_sketch"]
        assert idea["novelty_claim"] and idea["risks"] and idea["required_resources"]
        assert set(idea["source_paper_ids"]) <= {PAPER_A, PAPER_B}
        assert len(set(idea["source_paper_ids"])) >= 2, "跨论文整合需要至少两篇来源"
        assert 0.0 <= idea["confidence"] <= 1.0


async def test_mock_ideation_never_invents_corpus_ids() -> None:
    """Without evidence the mock yields a placeholder that validation must reject."""
    payload = await MockResearchProvider().generate_json(
        system_prompt="sys", user_prompt="（无命中）", purpose="ideation"
    )

    known = {paper["id"] for paper in PAPERS}
    for idea in payload["ideas"]:
        assert not set(idea["source_paper_ids"]) & known


async def test_mock_critique_scores_are_bounded() -> None:
    payload = await MockResearchProvider().generate_json(
        system_prompt="sys", user_prompt="{}", purpose="critique"
    )

    for key in ("novelty", "feasibility", "evidence_support", "risk"):
        assert 0.0 <= payload[key] <= 1.0
    assert payload["verdict"] and payload["unsupported_claims"] and payload["suggested_fix"]


async def test_mock_direction_echoes_idea_ids_and_parent() -> None:
    payload = await MockResearchProvider().generate_json(
        system_prompt="sys", user_prompt=DIRECTION_PROMPT, purpose="direction"
    )

    direction = payload["directions"][0]
    assert direction["member_idea_ids"] == ["idea-0123456789ab", "idea-fedcba987654"]
    assert direction["parent_direction_id"] == "dir-0123456789ab"
    assert direction["name"] and direction["question"] and direction["gap_analysis"]
    assert direction["roadmap"] and direction["success_metrics"] and direction["open_risks"]
    assert 0.0 <= direction["priority"] <= 1.0


async def test_mock_experiment_is_actionable_and_lists_followups() -> None:
    payload = await MockResearchProvider().generate_json(
        system_prompt="sys",
        user_prompt="研究方向：决策点安全约束\n方向ID：dir-0123456789ab",
        purpose="experiment",
    )

    assert payload["objective"].startswith("验证 决策点安全约束")
    assert payload["protocol_steps"] and payload["ablations"] and payload["metrics"]
    assert payload["datasets"] and payload["baselines"]
    assert payload["falsification_criteria"] and payload["compute_estimate"]
    assert payload["timeline"] and payload["risks"]
    followups = payload["followups"]
    assert followups
    for item in followups:
        assert item["kind"] in FOLLOWUP_KINDS
        assert item["query"] and item["reason"]


async def test_mock_records_calls_and_rejects_unknown_purposes() -> None:
    provider = MockResearchProvider()

    with pytest.raises(ProviderError) as error:
        await provider.generate_json(system_prompt="s", user_prompt="u", purpose="translate")

    assert "不支持任务类型" in str(error.value)
    # The purpose is recorded before dispatch, so the failed call is still visible.
    assert provider.calls == ["translate"]


def test_parse_json_content_accepts_bare_and_fenced_payloads() -> None:
    assert parse_json_content('{"a": 1}', "ideation") == {"a": 1}
    assert parse_json_content('```json\n{"a": 1}\n```', "ideation") == {"a": 1}
    assert parse_json_content('```\n{"a": 1}\n```', "ideation") == {"a": 1}


def test_parse_json_content_recovers_json_embedded_in_prose() -> None:
    content = '好的，结果如下：{"ideas": [{"title": "含 } 括号的标题"}]} 希望有帮助'

    parsed = parse_json_content(content, "ideation")

    assert parsed["ideas"][0]["title"] == "含 } 括号的标题"


@pytest.mark.parametrize(
    "content",
    ["", "   ", "not json at all", '{"broken": ', "[1, 2, 3]", '"just a string"'],
)
def test_parse_json_content_rejects_unusable_output(content: str) -> None:
    with pytest.raises(ProviderError) as error:
        parse_json_content(content, "deep_analysis")

    assert "deep_analysis" in str(error.value)


def test_build_provider_returns_the_mock_when_configured_for_offline_use(
    settings: ResearchSettings,
) -> None:
    assert isinstance(build_provider(settings), MockResearchProvider)


def test_build_provider_refuses_to_run_without_model_config(
    settings: ResearchSettings,
) -> None:
    unconfigured = dataclasses.replace(
        settings, llm_provider="openai_compatible", llm_base_url="", llm_model=""
    )

    with pytest.raises(ProviderError) as error:
        build_provider(unconfigured)

    message = str(error.value)
    assert "RESEARCH_LLM_BASE_URL" in message
    assert "RESEARCH_LLM_MODEL" in message
    assert "mock" in message


def test_build_provider_returns_the_http_provider_once_configured(
    settings: ResearchSettings,
) -> None:
    configured = dataclasses.replace(
        settings,
        llm_provider="openai_compatible",
        llm_base_url="https://example.com/v1/",
        llm_api_key="sk-test",
        llm_model="strong-model",
    )

    provider = build_provider(configured)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.endpoint == "https://example.com/v1/chat/completions"


def test_http_provider_requires_a_model_name(settings: ResearchSettings) -> None:
    half_configured = dataclasses.replace(
        settings,
        llm_provider="openai_compatible",
        llm_base_url="https://example.com/v1",
        llm_model="",
    )

    with pytest.raises(ProviderError) as error:
        OpenAICompatibleProvider(half_configured)

    assert "未配置研究模型" in str(error.value)


def test_http_provider_keeps_an_explicit_completions_path(
    settings: ResearchSettings,
) -> None:
    configured = dataclasses.replace(
        settings,
        llm_provider="openai_compatible",
        llm_base_url="https://example.com/v1/chat/completions",
        llm_model="strong-model",
    )

    provider = OpenAICompatibleProvider(configured)

    assert provider.endpoint == "https://example.com/v1/chat/completions"


def test_proxy_detection_skips_socks_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    """httpx cannot tunnel SOCKS here; picking one would break every call."""
    for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    assert _proxy_url() is None

    monkeypatch.setenv("ALL_PROXY", "socks5h://127.0.0.1:7890")
    assert _proxy_url() is None

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")
    assert _proxy_url() == "http://127.0.0.1:8888"
