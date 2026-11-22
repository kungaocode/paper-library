from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryDefinition:
    id: str
    directory: str
    index: int
    name_zh: str
    name_en: str
    description: str
    representative_titles: tuple[str, ...]


CATEGORIES: tuple[CategoryDefinition, ...] = (
    CategoryDefinition(
        id="cat-01",
        directory="01_微调安全_机理与测量",
        index=1,
        name_zh="微调安全：机理与测量",
        name_en="Fine-tuning Safety: Mechanisms and Measurement",
        description="微调为什么会破坏对齐、安全能力如何在表示和输出层发生漂移，以及如何测量这种退化。",
        representative_titles=(
            "Fine-tuning Aligned Language Models Compromises Safety",
            "Refusal in Language Models Is Mediated by a Single Direction",
            "Navigating the Safety Landscape",
        ),
    ),
    CategoryDefinition(
        id="cat-02",
        directory="02_微调安全_防御方法",
        index=2,
        name_zh="微调安全：防御方法",
        name_en="Fine-tuning Safety: Defenses",
        description="训练前、训练中和训练后的安全保持技术，包括安全约束、模型合并、安全 LoRA 与数据防御。",
        representative_titles=(
            "Safe LoRA",
            "SafeMERGE",
            "Safety-Aware Probing Optimization",
        ),
    ),
    CategoryDefinition(
        id="cat-03",
        directory="03_越狱攻击与防御",
        index=3,
        name_zh="越狱攻击与防御",
        name_en="Jailbreak Attacks and Defenses",
        description="对抗后缀、多轮越狱、多模态越狱、通用对抗扰动词和输入侧防御。",
        representative_titles=(
            "Universal and Transferable Adversarial Attacks on Aligned Language Models",
            "SmoothLLM",
            "MultiBreak",
        ),
    ),
    CategoryDefinition(
        id="cat-04",
        directory="04_智能体安全与提示注入",
        index=4,
        name_zh="智能体安全与提示注入",
        name_en="Agent Security and Prompt Injection",
        description="间接提示注入、工具链攻击面和具身智能体行动层操纵。",
        representative_titles=(
            "Indirect Prompt Injection",
            "LLM Agents can Autonomously Hack Websites",
            "Jailbreaking Embodied LLMs via Action-Level Manipulation",
        ),
    ),
    CategoryDefinition(
        id="cat-05",
        directory="05_评测基准与工具",
        index=5,
        name_zh="评测基准与工具",
        name_en="Evaluation Benchmarks and Tooling",
        description="安全评测、可信度指标、偏好实验、自动评分和漏洞扫描基础设施。",
        representative_titles=("HELM", "TrustLLM", "garak", "AlpacaEval"),
    ),
    CategoryDefinition(
        id="cat-06",
        directory="06_对齐_数据与偏好优化",
        index=6,
        name_zh="对齐、数据与偏好优化",
        name_en="Alignment, Data and Preference Optimization",
        description="RLHF、DPO、自生成指令、数据筛选与偏好优化算法。",
        representative_titles=("InstructGPT", "Direct Preference Optimization", "Self-Instruct", "LIMA"),
    ),
    CategoryDefinition(
        id="cat-07",
        directory="07_参数高效微调",
        index=7,
        name_zh="参数高效微调",
        name_en="Parameter-Efficient Fine-tuning",
        description="LoRA、QLoRA、DoRA 等低成本适配和量化微调方法。",
        representative_titles=("LoRA", "QLoRA", "DoRA"),
    ),
    CategoryDefinition(
        id="cat-08",
        directory="08_推理与思维链",
        index=8,
        name_zh="推理与思维链",
        name_en="Reasoning and Chain-of-Thought",
        description="思维链、测试时计算、过程监督、自反思和推理可靠性。",
        representative_titles=(
            "Chain-of-Thought Prompting",
            "Let's Verify Step by Step",
            "DeepSeek-R1",
        ),
    ),
    CategoryDefinition(
        id="cat-09",
        directory="09_规划与LLM-Modulo",
        index=9,
        name_zh="规划与 LLM-Modulo",
        name_en="Planning and LLM-Modulo",
        description="LLM 规划能力、经典规划结合、可验证规划和 LLM-Modulo 框架。",
        representative_titles=("LLM-Modulo", "LLM+P", "SafeRun"),
    ),
    CategoryDefinition(
        id="cat-10",
        directory="10_智能体与工具使用",
        index=10,
        name_zh="智能体与工具使用",
        name_en="Agents and Tool Use",
        description="工具调用、网页智能体、环境交互、反思和多工具协同。",
        representative_titles=("ReAct", "Toolformer", "WebArena", "VOYAGER"),
    ),
    CategoryDefinition(
        id="cat-11",
        directory="11_检索增强生成",
        index=11,
        name_zh="检索增强生成",
        name_en="Retrieval-Augmented Generation",
        description="检索增强生成、自反思检索、纠错检索和 RAG 评测。",
        representative_titles=("Retrieval-Augmented Generation", "Self-RAG", "CRAG", "RAGAS"),
    ),
    CategoryDefinition(
        id="cat-12",
        directory="12_安全范式与综述",
        index=12,
        name_zh="安全范式与综述",
        name_en="Security Paradigms and Surveys",
        description="体系级安全范式、内生安全机制和 LLM 安全隐私综述。",
        representative_titles=("内生安全", "A Survey on LLM Security and Privacy"),
    ),
)

CATEGORY_BY_ID = {category.id: category for category in CATEGORIES}
CATEGORY_BY_NAME = {category.name_zh: category for category in CATEGORIES}
