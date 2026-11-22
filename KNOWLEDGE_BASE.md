# 论文知识库 / Paper Knowledge Base

> 大模型安全方向的论文阅读卡片集合。所有 PDF 已按真实标题重命名，存放在 `completed/` 下的 12 个主题子目录中。
> 本文件按同样的主题分组，每篇论文一条记录：核心论点（中）/ 创新点（中）/ Core thesis (EN) / Novelty (EN)。
> 新论文请先放进 `need_organization/`，整理后追加条目到对应主题分组，并在下表登记。

- 论文总数：**68**（已整理）
- 重复副本与旧版本：`_archive/duplicates/`、`_archive/versions/`（未删除，仅归档）
- 最后更新：2026-10-21

## 目录 / Index

1. [微调安全：机理与测量](#1-微调安全机理与测量) (3)
2. [微调安全：防御方法](#2-微调安全防御方法) (5)
3. [越狱攻击与防御](#3-越狱攻击与防御) (7)
4. [智能体安全与提示注入](#4-智能体安全与提示注入) (3)
5. [评测基准与工具](#5-评测基准与工具) (5)
6. [对齐、数据与偏好优化](#6-对齐数据与偏好优化) (11)
7. [参数高效微调](#7-参数高效微调) (3)
8. [推理与思维链](#8-推理与思维链) (10)
9. [规划与 LLM-Modulo](#9-规划与-llm-modulo) (6)
10. [智能体与工具使用](#10-智能体与工具使用) (8)
11. [检索增强生成](#11-检索增强生成) (4)
12. [安全范式与综述](#12-安全范式与综述) (3)

---

## 1. 微调安全：机理与测量

**主题定位**：回答"微调为什么会破坏对齐""安全性在模型里以什么形式存在"。这一组是全部微调防御方法（第 2 组）的机理依据。

### Fine-tuning Aligned Language Models Compromises Safety, Even When Users Do Not Intend To（Qi et al., ICLR 2024）

- **PDF**：[01_微调安全_机理与测量/Fine-tuning Aligned Language Models Compromises Safety, Even When Users Do Not Intend To.pdf](</home/kun/Desktop/paper/completed/01_微调安全_机理与测量/Fine-tuning Aligned Language Models Compromises Safety, Even When Users Do Not Intend To.pdf>)
- **核心论点（中）**：即使只用少量完全良性的数据做常规微调，对齐后模型的安全性也会被明显削弱；微调接口本身就是攻击面。作者进一步证明：后端被植入后门的模型在"提示 + 触发词"组合下可以大幅绕过安全过滤。
- **创新点（中）**：首次把微调攻击从"必须投毒数据"扩展到"良性数据也危险"这一设定；给出可复现的低成本攻击配方（仅 10 条样例、通过公开 API 花费不到 0.20 美元即可越狱 GPT-3.5 Turbo）；提出用安全评估集的变化量量化微调带来的安全退化。
- **Core thesis (EN)**: Benign fine-tuning alone degrades safety alignment, so the fine-tuning interface is itself a threat vector. A backdoored model released as a "safe" fine-tuned checkpoint can be activated at prompt level, reaching 63.3% attack success rate once a trigger is appended.
- **Novelty (EN)**: Reframes fine-tuning APIs as an attack surface rather than only a data-mixing problem, and ships a reproducible jailbreak using 10 examples and under USD 0.20 of API spend on GPT-3.5 Turbo, plus a protocol for measuring safety loss during fine-tuning.

### Navigating the Safety Landscape: Measuring Risks in Finetuning Large Language Models（Peng et al., arXiv:2405.17374）

- **PDF**：[01_微调安全_机理与测量/Navigating the Safety Landscape - Measuring Risks in Finetuning Large Language Models.pdf](</home/kun/Desktop/paper/completed/01_微调安全_机理与测量/Navigating the Safety Landscape - Measuring Risks in Finetuning Large Language Models.pdf>)
- **核心论点（中）**：微调后的安全风险不是随机出现的，而是由权重在"安全盆地（safety basin）"中的位置决定。只要扰动仍落在对齐模型所在的局部盆地内，拒绝能力得以保持；一旦跨出盆地边界，安全性呈阶梯式崩塌。
- **创新点（中）**：用与任务无关的随机权重扰动作为探针，把安全退化解释成损失景观上的几何现象；指出能力在初始点最强、随扰动单调衰减；据此提出无需有害样本集的安全度量 VISAGE，用于刻画微模型相对基座的安全偏移。
- **Core thesis (EN)**: Post-fine-tuning risk is governed by whether weights stay inside the local "safety basin" of the aligned model. Inside the basin refusal survives; crossing the boundary produces a step-like collapse, while capability peaks at initialization and decays monotonically with perturbation.
- **Novelty (EN)**: Turns risk measurement into a loss-landscape geometry problem using task-agnostic random weight perturbations, and introduces the VISAGE metric for scoring safety drift without curated harmful benchmarks.

### Refusal in Language Models Is Mediated by a Single Direction（Arditi et al., NeurIPS 2024）

- **PDF**：[01_微调安全_机理与测量/Refusal in Language Models Is Mediated by a Single Direction.pdf](</home/kun/Desktop/paper/completed/01_微调安全_机理与测量/Refusal in Language Models Is Mediated by a Single Direction.pdf>)
- **核心论点（中）**：开源对话模型的拒绝行为由残差流中的一个一维方向控制。只需沿这一个方向做表示消融（把它从激活中减掉），模型就失去拒绝能力，而通用性能几乎不受影响。
- **创新点（中）**：把"安全对齐"这种看似分布式的高层行为压缩成单向量级的可操作对象；由此导出完全白盒、无需优化、无需对抗后缀的"外科手术式"越狱；并提供从权重层面检测安全行为被微调换掉的取证手段。
- **Core thesis (EN)**: Across 13 open-source chat models up to 72B parameters, refusal is mediated by a one-dimensional subspace; ablating that single direction removes refusal while leaving general capability intact.
- **Novelty (EN)**: Gives a mechanistic account of safety alignment as a single direction, enabling a white-box surgical jailbreak with no optimization or adversarial suffix, plus a weight-level forensic test for detecting safety-suppressing fine-tuning.

---

## 2. 微调安全：防御方法

**主题定位**：在第 1 组的机理结论上给出可落地的防御。三条技术路线：训练期约束（PACT、SAP）、结构化微调补丁（Safe LoRA）、训练后权重合并（SafeMERGE、Pre/Post-Tuning Merging）。

### Few Tokens, Big Leverage: Preserving Safety Alignment by Constraining Safety Tokens during Fine-tuning（Wang, Shi, Ouyang, Wang, KDD 2026）

- **PDF**：[02_微调安全_防御方法/Few Tokens Big Leverage - Preserving Safety Alignment by Constraining Safety Tokens during Fine-tuning.pdf](</home/kun/Desktop/paper/completed/02_微调安全_防御方法/Few Tokens Big Leverage - Preserving Safety Alignment by Constraining Safety Tokens during Fine-tuning.pdf>)
- **核心论点（中）**：安全性并不弥散在整个词表上，而是集中在极少数"safety tokens"上。微调越狱的本质是这些token上的置信度被压低，因此只要把它们的安全置信度锚定到对齐参考模型，就能在保留下游任务性能的同时守住安全。
- **创新点（中）**：提出 PACT（以安全token为约束的微调目标），把防御粒度从"整个模型/整个损失"收窄到"一小撮关键token"；论文给出的机制证据是：增强被识别出的 50 个安全token可把 ASR 从 33.5% 压到 0.5%，消融它们则升到 41.5%，而随机选token几乎无影响；方法无需安全数据、只多一个正则项。
- **Core thesis (EN)**: Safety knowledge concentrates on a small subset of safety tokens, and jailbreak-by-fine-tuning works by suppressing their confidence. Regularizing confidence on exactly those tokens, toward the aligned reference model, preserves safety without hurting task utility.
- **Novelty (EN)**: Reduces defensive scope from whole-model or whole-loss constraints to a handful of tokens with causal evidence (boosting the identified 50 safety tokens drops ASR from 33.5% to 0.5%; ablating them raises it to 41.5%; random tokens do nothing). The resulting PACT objective is data-free and adds only a regularizer.

### Mitigating Fine-tuning Risks in LLMs via Safety-Aware Probing Optimization (SAP)（北京大学, arXiv:2505.16737）

- **PDF**：[02_微调安全_防御方法/Mitigating Fine-tuning Risks in LLMs via Safety-Aware Probing Optimization (SAP).pdf](</home/kun/Desktop/paper/completed/02_微调安全_防御方法/Mitigating Fine-tuning Risks in LLMs via Safety-Aware Probing Optimization (SAP).pdf>)
- **核心论点（中）**：与其在微调后检测风险，不如在梯度传播过程中就把安全信号纳入优化。SAP 在训练回路里插入一个安全感知探针，使每一步参数更新同时受到任务损失和安全探针的引导。
- **创新点（中）**：把"探针（probing）"从离线分析工具变成在线训练组件，让安全约束参与反向传播；在测试损失与标准微调相当的前提下显著降低输出有害性，说明安全与效用并非必须二选一。
- **Core thesis (EN)**: Safety signals should participate in gradient propagation instead of being checked afterwards. A safety-aware probe embedded in the training loop steers every update, reducing harmfulness below standard fine-tuning while keeping comparable test loss.
- **Novelty (EN)**: Converts probing, normally an offline interpretability tool, into an in-loop optimization component, demonstrating that safety and utility can be retained simultaneously rather than traded off.

### Safe LoRA: the Silver Lining of Reducing Safety Risks when Fine-tuning Large Language Models（arXiv:2405.16833）

- **PDF**：[02_微调安全_防御方法/Safe LoRA - the Silver Lining of Reducing Safety Risks when Fine-tuning Large Language Models.pdf](</home/kun/Desktop/paper/completed/02_微调安全_防御方法/Safe LoRA - the Silver Lining of Reducing Safety Risks when Fine-tuning Large Language Models.pdf>)
- **核心论点（中）**：安全能力的漂移可以在 LoRA 权重层面被纠正。Safe LoRA 把选定层的 LoRA 权重投影回"安全对齐子空间"，于是低秩微调既能学到任务，又不会把模型推出安全区域。
- **创新点（中）**：一种免训练、免数据的"一行代码级"补丁：只需要基座模型与对齐模型两套权重即可构造投影子空间，不需要任何额外安全语料或训练轮次；并指出只有少数层对安全漂移负责，因此可选择性施加。
- **Core thesis (EN)**: Safety drift can be corrected at the LoRA-weight level. Projecting the LoRA weights of selected layers back onto the safety-aligned subspace lets low-rank fine-tuning acquire the task without pushing the model out of the safe region.
- **Novelty (EN)**: A training-free, data-free one-liner patch that needs only the base and aligned weight sets to build the projection subspace, plus the layer-localization finding that a few layers dominate safety drift.

### SafeMERGE: Preserving Safety Alignment in Fine-Tuned LLMs via Selective Layer-Wise Model Merging（TU Muenchen + IBM）

- **PDF**：[02_微调安全_防御方法/SafeMERGE - Preserving Safety Alignment in Fine-Tuned LLMs via Selective Layer-Wise Model Merging.pdf](</home/kun/Desktop/paper/completed/02_微调安全_防御方法/SafeMERGE - Preserving Safety Alignment in Fine-Tuned LLMs via Selective Layer-Wise Model Merging.pdf>)
- **核心论点（中）**：微调后的模型不必整体回滚。用逐层余弦相似度偏离度作为门控，只在"安全偏离明显"的层把微调权重与对齐权重合并，其余层保留任务收益，即可事后修复安全。
- **创新点（中）**：把模型合并从全局超参调优变成层级别的选择性操作，判据是无害的表示相似度而非安全数据；在 4 个 LLM 上验证，属于纯后处理，不增加训练成本。
- **Core thesis (EN)**: A fine-tuned model need not be rolled back wholesale. Gating on per-layer cosine-similarity deviation and merging aligned weights only into the layers that drift on safety repairs safety while retaining task gains elsewhere.
- **Novelty (EN)**: Turns model merging from a global hyperparameter blend into a layer-selective operation keyed on benign representation similarity rather than safety data; purely post-hoc, verified on four LLMs with no extra training cost.

### Safeguard Fine-Tuned LLMs Through Pre- and Post-Tuning Model Merging（NTU + Intel, arXiv:2412.19512）

- **PDF**：[02_微调安全_防御方法/Safeguard Fine-Tuned LLMs Through Pre- and Post-Tuning Model Merging.pdf](</home/kun/Desktop/paper/completed/02_微调安全_防御方法/Safeguard Fine-Tuned LLMs Through Pre- and Post-Tuning Model Merging.pdf>)
- **核心论点（中）**：防御可以完全绕开"安全数据"这一瓶颈：在微调前把对齐模型与基座模型合并形成一个本身就稳健的起点，在微调后再合并一次做修复，双端夹击保住安全。
- **创新点（中）**：同一套权重合并思想同时用于训练前与训练后两个阶段，构成闭环而非单点后处理；不需要额外安全语料、不需要改动训练目标，因此对第三方微调管线（API 用户、开源权重发布者）几乎零迁移成本。
- **Core thesis (EN)**: Safety can be preserved without any safety dataset by merging the aligned model with the base model before fine-tuning to create a robust starting point, then merging again afterwards to repair residual drift.
- **Novelty (EN)**: Applies the same weight-merging idea at both ends of training as a closed loop instead of a single post-hoc step, requiring no safety corpus and no change to the training objective, so it drops into third-party fine-tuning pipelines at near-zero migration cost.

---

## 3. 越狱攻击与防御

**主题定位**：对抗样本从视觉（FGSM/PGD）迁移到语言模型（GCG/ADC）的攻击谱系，多轮与多模态扩展（MultiBreak、AAAI-26），以及对应的表示层/平滑层防御（SmoothLLM）。

### Explaining and Harnessing Adversarial Examples（FGSM, Goodfellow, Shlens, Szegedy, ICLR 2015）

- **PDF**：[03_越狱攻击与防御/Explaining and Harnessing Adversarial Examples (FGSM).pdf](</home/kun/Desktop/paper/completed/03_越狱攻击与防御/Explaining and Harnessing Adversarial Examples (FGSM).pdf>)
- **核心论点（中）**：深度模型的脆弱性主要来自其高度非线性以及高维输入空间中的"线性泄漏"：沿损失梯度方向给输入加一个极小的、人眼不可察觉的扰动，就能翻转分类结果。对抗样本因此不是 bug，而是模型泛化方式的副产品。
- **创新点（中）**：给出一步即成的单梯度攻击 FGSM（ε 球内取符号化梯度），使攻击成本降到接近一次前向 + 一次反向；同时把对抗训练形式化为"在 ε 球内最大化损失"的极小极大目标，成为此后所有鲁棒性工作的共同语言。
- **Core thesis (EN)**: Deep networks are brittle because of linear-ish behaviour in high-dimensional input space: adding a tiny, imperceptible perturbation along the loss gradient flips the prediction. Adversarial examples are a side effect of how models generalize, not an implementation bug.
- **Novelty (EN)**: Introduces FGSM, a one-step attack costing roughly one forward and one backward pass (signed gradient within an epsilon ball), and frames adversarial training as a min-max objective that maximizes loss inside that ball, the shared vocabulary for all later robustness work.

### Towards Deep Learning Models Resistant to Adversarial Attacks（PGD, Madry et al., ICLR 2018）

- **PDF**：[03_越狱攻击与防御/Towards Deep Learning Models Resistant to Adversarial Attacks (PGD).pdf](</home/kun/Desktop/paper/completed/03_越狱攻击与防御/Towards Deep Learning Models Resistant to Adversarial Attacks (PGD).pdf>)
- **核心论点（中）**：要真正评估并提升鲁棒性，必须假设攻击者最强。作者把对抗训练明确写成 ε 约束下的最坏情形优化，并提出迭代多步、带随机起点与步长投影的 PGD 作为该内层问题的近似最优一阶攻击。
- **创新点（中）**：给出"一阶攻击的普遍性假设（First-Order Method Possesses）"作为合理性论证，使 PGD 成为此后公认的强攻击标准与鲁棒性评测基准；同时说明此前防御失败多因梯度掩蔽，而非真的鲁棒。
- **Core thesis (EN)**: Robustness claims require a strong adversary. Adversarial training is formulated explicitly as worst-case optimization under an L∞ epsilon constraint, with PGD, an iterative multi-step attack using random restarts and projection, as the near-optimal first-order solver for the inner problem.
- **Novelty (EN)**: Establishes the standard strong attack for evaluation, justified by a "First-Order Method Possesses" conjecture, and shows that earlier apparent robustness was largely gradient masking rather than genuine worst-case resistance.

### Universal and Transferable Adversarial Attacks on Aligned Language Models（GCG, Zou et al., 2023）

- **PDF**：[03_越狱攻击与防御/Universal and Transferable Adversarial Attacks on Aligned Language Models (GCG).pdf](</home/kun/Desktop/paper/completed/03_越狱攻击与防御/Universal and Transferable Adversarial Attacks on Aligned Language Models (GCG).pdf>)
- **核心论点（中）**：对齐后的对话模型同样存在对抗漏洞。一个与问题无关的通配恶意后缀即可让多个主流模型答非所问地输出有害内容，而且这个后缀在模型之间可迁移、对黑盒线上系统依然有效。
- **创新点（中）**：把 LLM 越狱变成一个可优化的对象：用梯度引导的贪心搜索在离散 token 空间里生成对抗后缀（多采样求和以缓解离散性），再把它作为输入拼接实现通用攻击；确立了后续几乎所有自动越狱方法与评测的基线。
- **Core thesis (EN)**: Aligned chat models have adversarial vulnerabilities too. A single question-agnostic malicious suffix, optimized once, elicits harmful answers across many production models, transfers between models, and still works against black-box APIs.
- **Novelty (EN)**: Turns jailbreaking into a concrete optimization object by using gradient-guided greedy search over discrete tokens (multi-sampling to smooth the discrete space) to produce a universal adversarial suffix, setting the baseline that nearly all subsequent automated jailbreak and defense work measures against.

### Efficient LLM Jailbreak via Adaptive Dense-to-sparse Constrained Optimization (ADC)（Hu et al., NeurIPS 2024）

- **PDF**：[03_越狱攻击与防御/Efficient LLM Jailbreak via Adaptive Dense-to-sparse Constrained Optimization (ADC).pdf](</home/kun/Desktop/paper/completed/03_越狱攻击与防御/Efficient LLM Jailbreak via Adaptive Dense-to-sparse Constrained Optimization (ADC).pdf>)
- **核心论点（中）**: 越狱后缀的长度本身就是代价：越长越容易被过滤规则与人眼发现。ADC 把越狱写成"在长度约束下最大化越狱成功率"的约束优化问题，用稠密到稀疏的自适应退火求解，从而在同样甚至更高的 ASR 下得到更短的后缀。
- **创新点（中）**：首次将长度作为显式约束引入自动越狱优化；在 AdvBench（520 条）上对 Llama2-chat-7B 取得 96.2% ASR，而 GCG 为 53.8%，且只用约 0.93 倍计算、墙钟时间约为其一半；在 Harmbench 的 8 个模型中有 7 个取得最高 ASR。
- **Core thesis (EN)**: Suffix length is itself a cost, since longer strings are more likely to be filtered or noticed. ADC casts jailbreaking as length-constrained optimization that maximizes success rate, solved by adaptive dense-to-sparse annealing, yielding shorter suffixes at equal or higher ASR.
- **Novelty (EN)**: First automatic jailbreak to treat length as an explicit constraint in the optimization. On AdvBench (520 prompts) it reaches 96.2% ASR on Llama2-chat-7B versus 53.8% for GCG using about 0.93x compute and roughly half the wall clock, and tops 7 of 8 Harmbench models.

### Efficient LLM-Jailbreaking via Multimodal-LLM Jailbreak（Ji, Lin, Niu, Gao, Hua, AAAI 2026）

- **PDF**：[03_越狱攻击与防御/Efficient LLM-Jailbreaking via Multimodal-LLM Jailbreak (AAAI-26).pdf](</home/kun/Desktop/paper/completed/03_越狱攻击与防御/Efficient LLM-Jailbreaking via Multimodal-LLM Jailbreak (AAAI-26).pdf>)
- **核心论点（中）**：越狱不一定要直接攻击目标 LLM。若存在以该 LLM 为语言主干的多模态模型，可以先越狱这个"更容易攻破的替身"，再把得到的越狱样本转换回纯文本，迁移攻击原来的 LLM，攻击成本大幅下降。
- **创新点（中）**：提出"经多模态替身间接越狱"的新攻击路径，并给出嵌入空间到文本空间的转换方法；白盒实验中经 MiniGPT4 攻击 LLaMA2 平均 ASR 达 85.0/84.7/78.6，显著高于 GCG 的 52.9，而运行时间只有 GCG 的约 3%（0.32 小时对 11.2 小时）；黑盒设定下对 Mistral-v0.3、Gemma2、Deepseek-R1、Grok-3、DouBao1.5 同样有效。
- **Core thesis (EN)**: Jailbreaking need not target the LLM directly. When a multimodal model uses that LLM as its language backbone, jailbreaking the softer proxy first and converting the resulting embeddings back into text yields an indirect, far cheaper attack on the original LLM.
- **Novelty (EN)**: Opens an indirect attack route through a multimodal stand-in plus an embedding-to-text conversion. White-box: attacking LLaMA2 via MiniGPT4 averages 85.0/84.7/78.6 ASR against GCG's 52.9, in about 3% of GCG's runtime (0.32h vs 11.2h); the black-box variant also works on Mistral-v0.3, Gemma2, Deepseek-R1, Grok-3 and DouBao1.5.

### MultiBreak: A Scalable and Diverse Multi-turn Jailbreak Benchmark for Evaluating LLM Safety（Microsoft / Columbia / JHU, arXiv:2605.01687）

- **PDF**：[03_越狱攻击与防御/MultiBreak - A Scalable and Diverse Multi-turn Jailbreak Benchmark for Evaluating LLM Safety.pdf](</home/kun/Desktop/paper/completed/03_越狱攻击与防御/MultiBreak - A Scalable and Diverse Multi-turn Jailbreak Benchmark for Evaluating LLM Safety.pdf>)
- **核心论点（中）**：单轮越狱基准无法反映真实对话中的渐进式诱导。把越狱拆成跨轮次展开的多步意图后，多轮攻击的成功率远高于单轮，而现有数据集在多轮设定下规模与多样性都不足。
- **创新点（中）**：构建可扩展、多样化的多轮越狱基准：10,389 条多轮提示、覆盖 2,665 个有害意图；在 DeepSeek-R1-7B 与 GPT-4.1-mini 上，相对次优数据集分别把 ASR 抬高 54.0% 与 34.6%；还给出主动学习式的攻击者策略，5 轮内即在 Qwen2.5 上突破 50% ASR。
- **Core thesis (EN)**: Single-turn jailbreak benchmarks miss how real conversations escalate. Decomposing a jailbreak into multi-step intent spread over turns gives markedly higher attack success, and existing datasets are too small and too uniform to measure this.
- **Novelty (EN)**: A scalable, diverse multi-turn benchmark of 10,389 multi-turn prompts over 2,665 harmful intents, raising ASR by up to 54.0% and 34.6% over the second-best dataset on DeepSeek-R1-7B and GPT-4.1-mini, plus an active-learning attacker that exceeds 50% ASR within 5 rounds on Qwen2.5.

### SmoothLLM: Defending Large Language Models Against Jailbreaking Attacks（Robey et al., UPenn, 2023）

- **PDF**：[03_越狱攻击与防御/SmoothLLM - Defending Large Language Models Against Jailbreaking Attacks.pdf](</home/kun/Desktop/paper/completed/03_越狱攻击与防御/SmoothLLM - Defending Large Language Models Against Jailbreaking Attacks.pdf>)
- **核心论点（中）**：对抗后缀之所以奏效，是因为它是最小扰动的恶意序列。SmoothLLM 对输入做字符级随机扰动生成 N 个副本、分别询问模型再聚合投票，任何依赖精确字符序列的对抗后缀都会在扰动空间中被破坏掉。
- **创新点（中）**：把随机平滑这一经典鲁棒性技术移植到 LLM 文本输入，且不需要重训模型；在 GCG、PAIR、RandomSearch、AmpleGCG 上均取得当时最佳防御效果，对专门针对本防御的自适应 GCG 攻击仍保持稳健，代价只是很小的鲁棒性-效用折衷与额外的推理次数。
- **Core thesis (EN)**: Adversarial suffixes work precisely because they are minimal perturbations of a malicious string. SmoothLLM randomly perturbs the input at character level into N copies, queries the model on each and aggregates by majority vote, destroying suffixes that depend on exact character sequences.
- **Novelty (EN)**: Ports randomized smoothing, a classical robustness technique, to LLM text inputs with no retraining; achieves state-of-the-art defense against GCG, PAIR, RandomSearch and AmpleGCG, stays robust even against an adaptive GCG tuned to defeat it, at a small robustness-utility trade-off plus extra inference cost.

---

## 4. 智能体安全与提示注入

**主题定位**：威胁从"单次对话"升级到"接入外部数据与真实系统的智能体"。核心是间接提示注入：把指令藏在数据里，让智能体替你做事。

### Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection（Abdelnabi et al. / CISPA, AISec 2023）

- **PDF**：[04_智能体安全与提示注入/Not What You've Signed Up For - Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection.pdf](</home/kun/Desktop/paper/completed/04_智能体安全与提示注入/Not What You%27ve Signed Up For - Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection.pdf>)
- **核心论点（中）**：LLM 应用无法区分"用户指令"与"外部数据"，因为二者最终都拼进同一个上下文。攻击者只需把指令写进智能体将来会读取的网页、邮件或文档里，就能控制应用行为，这是 LLM 集成软件的原生缺陷而非实现疏忽。
- **创新点（中）**：系统性提出并命名间接提示注入攻击面，给出覆盖真实工具链（插件、RAG、代码解释器、多智能体）的威胁分类：数据窃取、欺诈、worming（自我传播）、以及针对 RAG 后端与知识库的信息生态污染；并指出其对微软 Copilot 等实际部署的可行性。
- **Core thesis (EN)**: LLM applications cannot tell user instructions from external data because both end up concatenated in one context. An attacker only needs to plant instructions in a page, email or document the agent will later read, making this an intrinsic flaw of LLM-integrated software rather than an implementation slip.
- **Novelty (EN)**: Names and systematizes the indirect prompt injection threat surface across real tool chains (plugins, RAG, code interpreters, multi-agent systems), with a taxonomy spanning data exfiltration, fraud, self-propagating worming and poisoning of vector stores/knowledge bases, and demonstrates plausibility against shipped products such as Microsoft Copilot.

### LLM Agents can Autonomously Hack Websites（Wu et al., arXiv:2402.06664）

- **PDF**：[04_智能体安全与提示注入/LLM Agents can Autonomously Hack Websites.pdf](</home/kun/Desktop/paper/completed/04_智能体安全与提示注入/LLM Agents can Autonomously Hack Websites.pdf>)
- **核心论点（中）**：当智能体拥有记忆、多智能体协作与工具使用能力后，它能自主完成端到端的真实网站攻击，包括发现漏洞、构造跨 38 个动作的攻击链并窃取数据库，而不需要人类分步指挥。
- **创新点（中）**：把"智能体是否能自主攻击"从思辩变成可测量实验：在自建平台上评测，最佳配置达到 73.3% 成功率（15 个任务中 11 个，pass@5），攻击链包含 SQL union 注入等多步组合；同时证明现有安全评测集无法预测这种组合式自主危害。
- **Core thesis (EN)**: With memory, multi-agent collaboration and tool use, an LLM agent can carry out end-to-end attacks on real websites autonomously, finding vulnerabilities, chaining actions and exfiltrating databases without step-by-step human direction.
- **Novelty (EN)**: Turns "can agents self-drive an attack" into a measurable experiment, reaching 73.3% success (11 of 15 tasks, pass@5) with 38-action SQL-union chains on live sites, and shows that existing safety benchmarks fail to predict such compositional autonomous harm.

### Jailbreaking Embodied LLMs via Action-Level Manipulation (Blindfold)（PolyU + Cambridge, ACM SenSys 2026）

- **PDF**：[04_智能体安全与提示注入/Jailbreaking Embodied LLMs via Action-Level Manipulation (Blindfold).pdf](</home/kun/Desktop/paper/completed/04_智能体安全与提示注入/Jailbreaking Embodied LLMs via Action-Level Manipulation (Blindfold).pdf>)
- **核心论点（中）**：具身智能体的安全边界不在文本层，而在动作层。Blindfold 不去骗过语言模型的文字审查，而是在感知与执行之间篡改"动作计划"，让机器人执行危险动作却仍自认为在合法任务轨道上。
- **创新点（中）**：提出对抗性代理规划（Adversarial Proxy Planning）作为动作级越狱的通用框架，配合噪声掩蔽与基于规则的动作校验器绕过下游安全检查；相对当时最优攻击把 ASR 提高到 53 个百分点以上，并把越狱威胁从聊天模型扩展到物理执行系统。
- **Core thesis (EN)**: For embodied agents the safety boundary sits at the action level, not the text level. Blindfold does not defeat textual moderation but tampers with the action plan between perception and execution, so the robot performs dangerous actions while believing it is still on a legitimate task.
- **Novelty (EN)**: Introduces Adversarial Proxy Planning as a general action-level jailbreak frame, with noise concealment plus a rule-based action verifier to slip past downstream safety checks; lifts ASR by up to 53 percentage points over the prior best attack and moves the jailbreak threat from chat models to physical execution.

---

## 5. 评测基准与工具

**主题定位**：安全研究的可复现基础设施：能力/风险全景评测（HELM、TrustLLM）、偏好学习沙盒（AlpacaFarm）、评测去偏（LC-AlpacaEval）、自动化安全探针（garak）。

### Holistic Evaluation of Language Models（HELM, Liang et al., Stanford）

- **PDF**：[05_评测基准与工具/Holistic Evaluation of Language Models (HELM).pdf](</home/kun/Desktop/paper/completed/05_评测基准与工具/Holistic Evaluation of Language Models (HELM).pdf>)
- **核心论点（中）**：单一指标（例如准确率）无法描述一个语言模型的真实状态，评测必须"全景"。HELM 把"场景 × 指标"作为基本矩阵，在同一套统一代码库上对同一批模型同时测量准确率、校准、鲁棒性、公平性、偏见、毒性、多任务效能与资源消耗。
- **创新点（中）**：提出 7 项核心指标与场景化评测框架（16 个核心场景，另有 7 项目标性评测覆盖 26 个场景，共 42 个场景），并量化了一个事实：此前主流模型只覆盖约 17.9% 的（场景, 指标）组合，从而把"评测覆盖度"本身变成一个可统计对象。
- **Core thesis (EN)**: No single metric such as accuracy can characterize a language model, so evaluation must be holistic. HELM makes scenarios crossed with metrics the basic matrix and measures accuracy, calibration, robustness, fairness, bias, toxicity, multi-task efficacy and resource consumption for the same models in one unified codebase.
- **Novelty (EN)**: Defines the 7-metric by scenario framework (16 core scenarios plus 7 targeted evaluations over 26 scenarios, 42 scenarios in total) and quantifies that prior models covered only about 17.9% of the scenario-metric cells, turning evaluation coverage itself into a measurable quantity.

### TrustLLM: Trustworthiness in Large Language Models（Sun et al., arXiv 2024）

- **PDF**：[05_评测基准与工具/TrustLLM - Trustworthiness in Large Language Models.pdf](</home/kun/Desktop/paper/completed/05_评测基准与工具/TrustLLM - Trustworthiness in Large Language Models.pdf>)
- **核心论点（中）**："安全"只是可信的一个子集。作者把可信 LLM 拆成真实性、安全性、公平性、鲁棒性、隐私与机器伦理等相互独立又彼此约束的维度，并论证必须逐维度分别测量、分别归因。
- **创新点（中）**：给出一套跨 6 个维度、汇集 30 余个数据集的统一基准，评测 16 个主流 LLM，并把 utility（功能效果）与可信维度分开评估；同时把"各维度此消彼长"（如提升安全性可能损害真实性）显式报告为权衡曲线而非单点排名。
- **Core thesis (EN)**: Safety is only one facet of trustworthiness. The paper splits trustworthy LLMs into largely independent yet mutually constraining dimensions, truthfulness, safety, fairness, robustness, privacy and machine ethics, and argues each must be measured and attributed separately.
- **Novelty (EN)**: A unified benchmark spanning 6 dimensions over 30-plus datasets with 16 mainstream LLMs, separating utility from the trustworthiness dimensions, and reporting cross-dimension trade-offs explicitly rather than collapsing everything into one leaderboard.

### AlpacaFarm: A Simulation Framework for Methods that Learn from Human Feedback（Dubois et al., NeurIPS 2023）

- **PDF**：[05_评测基准与工具/AlpacaFarm - A Simulation Framework for Methods that Learn from Human Feedback.pdf](</home/kun/Desktop/paper/completed/05_评测基准与工具/AlpacaFarm - A Simulation Framework for Methods that Learn from Human Feedback.pdf>)
- **核心论点（中）**：人类偏好标注又贵又慢，使偏好学习算法的实验迭代被数据成本卡住。AlpacaFarm 用 LLM 模拟人类偏好、模拟对手模型与模拟评估者，搭出一个低成本但排名可信的完整训练沙盒。
- **创新点（中）**：LLM 模拟反馈的成本比众包标注低约 50 倍，且模拟排名与真实人类排名一致；框架内置 PPO、best-of-n、专家迭代等参考实现，把"新对齐算法能否公平比较"变成基础设施问题，并在 10k 偏好对、11 个模型上完成验证。
- **Core thesis (EN)**: Human preference annotation is expensive and slow, so preference-learning research is throttled by data cost. AlpacaFarm substitutes LLM-simulated preferences, simulated opponent models and simulated evaluators to build a cheap yet faithful training sandbox for full pipelines.
- **Novelty (EN)**: Shows LLM-simulated feedback is about 50x cheaper than crowdworkers while reproducing real-human rankings, ships reference PPO, best-of-n and expert-iteration implementations, and validates on 10k preference pairs across 11 models, turning fair algorithm comparison into an infrastructure problem.

### Length-Controlled AlpacaEval: A Simple Way to Debias Automatic Evaluators（Dubois et al., 2024）

- **PDF**：[05_评测基准与工具/Length-Controlled AlpacaEval - A Simple Way to Debias Automatic Evaluators.pdf](</home/kun/Desktop/paper/completed/05_评测基准与工具/Length-Controlled AlpacaEval - A Simple Way to Debias Automatic Evaluators.pdf>)
- **核心论点（中）**：LLM 裁判系统性地偏爱更长的回答，因此排行榜很大程度上在奖励"话多"。长度控制方法从因果推断角度出发，把回答长度作为混杂变量做去偏，得到与长度无关的质量信号。
- **创新点（中）**：只需在自动裁判的 logit 上加一个简单的长度回归校正即可实现，无需新标注数据；校正后 AlpacaEval 与 Chatbot Arena 的 Spearman 相关从 0.94 提升到 0.98，成为后续所有对话排行榜默认采用的长度控制口径。
- **Core thesis (EN)**: LLM judges systematically prefer longer answers, so leaderboards largely reward verbosity. Treating answer length as a confounder, length-controlled AlpacaEval de-biases the win rate to isolate quality from length.
- **Novelty (EN)**: Achieves this with a single length-regression correction on the judge's logits, no extra annotation, lifting the Spearman correlation with Chatbot Arena from 0.94 to 0.98 and becoming the default length-controlled reporting standard for chat leaderboards.

### garak: A Framework for Security Probing Large Language Models（NVIDIA）

- **PDF**：[05_评测基准与工具/garak - A Framework for Security Probing Large Language Models.pdf](</home/kun/Desktop/paper/completed/05_评测基准与工具/garak - A Framework for Security Probing Large Language Models.pdf>)
- **核心论点（中）**：LLM 安全不该靠一次性人工红队。garak 把它改造成自动化"探索式漏洞扫描"：像 nmap 那样对模型持续探测已知风险类别，输出可比较的失败清单而不是笼统的"安全分"。
- **创新点（中）**：提出 Generators / Probes / Detectors / Buffs 四段式解耦架构，探针、检测器与攻击增强器可独立扩展复用，从而把新论文里的越狱方法快速接入为一条探针；同时明确把"LLM 安全"重新表述为发现与探索问题，目前探针以英语为主。
- **Core thesis (EN)**: LLM security should not rely on one-off human red-teaming. garak recasts it as automated exploratory vulnerability scanning, probing models continuously for known risk categories like nmap does for hosts and emitting a comparable list of failures instead of a vague safety score.
- **Novelty (EN)**: A four-part decoupled architecture of Generators, Probes, Detectors and Buffs that lets new jailbreak papers be wired in as probes independently, and reframes "LLM security" as a discovery problem; probes are English-only for now.

---

## 6. 对齐、数据与偏好优化

**主题定位**：模型"会不会听话""听的是谁的话"的来源。三条脉络：偏好优化算法（InstructGPT → DPO → ORPO）、数据来源（Self-Instruct / WizardLM / AlpaGasus / Magpie / phi-1 / LIMA）、以及无需人类标注的路线（CAI）。

### Training Language Models to Follow Instructions with Human Feedback（InstructGPT, Ouyang et al., NeurIPS 2022）

- **PDF**：[06_对齐_数据与偏好优化/Training Language Models to Follow Instructions with Human Feedback (InstructGPT).pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/Training Language Models to Follow Instructions with Human Feedback (InstructGPT).pdf>)
- **核心论点（中）**：预训练目标（下一词预测）与"有用、诚实、无害"的用户意图并不对齐。用人类示范 + 人类偏好训练的 1.3B 模型，在人工评估上胜过 100 倍规模的 GPT-3 175B，说明对齐比参数量更能决定实际体验。
- **创新点（中）**：确立三阶段 RLHF 标准配方：SFT → 训练奖励模型 → PPO 强化学习，并引入 RL 微调与示范的混合目标抑制奖励攻击；同时提出"对齐税"概念与用对齐收益抵消它的做法，成为此后几乎所有指令模型的方法论底座。
- **Core thesis (EN)**: The pretraining objective (next-token prediction) is not aligned with user intent to be helpful, honest and harmless. A model trained on human demonstrations and human preferences (1.3B) is preferred over GPT-3 175B, roughly 100x larger, so alignment dominates raw parameter count.
- **Novelty (EN)**: Fixes the three-stage RLHF recipe, SFT then reward model then PPO, with a mixed objective combining RL fine-tuning and demonstration data to curb reward hacking, and names the "alignment tax" along with mitigations that trade capability for instruction following.

### Direct Preference Optimization: Your Language Model is Secretly a Reward Model（Rafailov et al., NeurIPS 2023）

- **PDF**：[06_对齐_数据与偏好优化/Direct Preference Optimization - Your Language Model is Secretly a Reward Model.pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/Direct Preference Optimization - Your Language Model is Secretly a Reward Model.pdf>)
- **核心论点（中）**：RLHF 里那个独立的奖励模型和 RL 循环在数学上是不必要的。DPO 把带 KL 约束的奖励最大化目标解析求解，得到"策略本身就是隐式奖励模型"的重参数化，于是可以直接用偏好对做分类式最大似然训练。
- **创新点（中）**：把偏好优化化简为一个闭式的二分类损失，免除奖励模型拟合、在线采样、逐 token 奖励与 RL 方差，工程上稳定且便宜；实验上与 PPO-based RLHF 相当或更好（IMDB、摘要、单轮对话），且对奖励模型的分布偏移更不敏感。
- **Core thesis (EN)**: The separate reward model and RL loop in RLHF are mathematically unnecessary. DPO solves the KL-constrained reward maximization objective in closed form, reparameterizing so that the policy itself is an implicit reward model, letting one fit preference pairs directly with a classification-style likelihood.
- **Novelty (EN)**: Reduces preference optimization to a closed-form binary cross-entropy loss, removing reward-model fitting, online sampling, per-token rewards and RL variance; matches or beats PPO-based RLHF on sentiment, summarization and single-turn dialogue while being less sensitive to reward-model distribution shift.

### ORPO: Monolithic Preference Optimization without Reference Model（Hong et al., 2024）

- **PDF**：[06_对齐_数据与偏好优化/ORPO - Monolithic Preference Optimization without Reference Model.pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/ORPO - Monolithic Preference Optimization without Reference Model.pdf>)
- **核心论点（中）**：对齐流程可以更激进地简化：SFT 与偏好优化本可以合并成单阶段。ORPO 在普通 SFT 损失上加一个"几率比（odds ratio）"惩罚项，直接压低被拒绝回答的相对几率，无需参考模型、无需偏好阶段。
- **创新点（中）**：完全免掉参考模型与显式 KL 约束，也免掉 DPO 之前的 SFT 步骤，把对齐压进一次训练；在 UltraFeedback 上对 Phi-2 (2.7B)、Llama-2 7B、Mistral 7B 验证，AlpacaEval 2 胜率等指标与 SFT+DPO 管线可比。
- **Core thesis (EN)**: SFT and preference optimization can be fused into a single stage. ORPO adds an odds-ratio penalty on rejected answers directly on top of the plain SFT loss, needing no reference model and no separate alignment phase.
- **Novelty (EN)**: Eliminates the reference model and explicit KL constraint as well as the SFT-before-DPO ordering, collapsing alignment into one training run; validated on UltraFeedback with Phi-2 2.7B, Llama-2 7B and Mistral 7B, staying competitive with SFT+DPO pipelines.

### Constitutional AI: Harmlessness from AI Feedback（Bai et al., Anthropic, 2022）

- **PDF**：[06_对齐_数据与偏好优化/Constitutional AI - Harmlessness from AI Feedback.pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/Constitutional AI - Harmlessness from AI Feedback.pdf>)
- **核心论点（中）**：无害性不必依赖大规模人工有害标注。给定一份成文原则（宪法），模型对自己有问题的输出进行批判并按原则改写，再用 AI 自己产生的偏好判断训练偏好模型，整个人类输入压缩为一份原则清单。
- **创新点（中）**：提出 SL-CAI（批判-改写自我改进）与 RL-CAI（RLAIF 用 AI 偏好取代人类偏好）两段式流程；把"价值观"外置成可读可改的显式文本，使安全行为可审计、可迭代，同时显著减少对人类标注者的心理暴露。
- **Core thesis (EN)**: Harmlessness does not require large-scale human harm labeling. Given a written constitution of principles, the model critiques and revises its own problematic outputs and an AI preference model is trained on AI-generated judgments, so the only human input is the principle list.
- **Novelty (EN)**: Introduces the SL-CAI critique-and-revise loop plus RL-CAI (RL from AI feedback), externalizing values into editable, auditable text and sharply reducing exposure of human annotators to harmful content.

### LIMA: Less Is More for Alignment（Zhou et al., Meta, NeurIPS 2023）

- **PDF**：[06_对齐_数据与偏好优化/LIMA - Less Is More for Alignment.pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/LIMA - Less Is More for Alignment.pdf>)
- **核心论点（中）**：对齐阶段的作用主要是"教模型输出的形式与风格"，而不是"教它知识"。仅用 1000 条精心挑选的高质量提示做 SFT、完全不用任何 RLHF，65B 模型即可产出接近 GPT-4 的对话质量。
- **创新点（中）**：把数据量的下限推到极致，并给出"超大规模偏好学习并非必需"的对照证据；在人工偏好评估中，LIMA 回答有 43% 与 GPT-4 打平或更优、58% 优于 Bard、65% 优于 DaVinci003；同时明确其局限：小数据无法带来新能力与鲁棒的拒答。
- **Core thesis (EN)**: Alignment mostly teaches the form and style of output, not knowledge. SFT on 1,000 hand-curated prompts with no RLHF at all yields a 65B model whose conversational quality approaches GPT-4.
- **Novelty (EN)**: Pushes the data-volume floor to the extreme and provides controlled evidence that huge preference-learning pipelines are not necessary: 43% of LIMA responses tie or beat GPT-4, 58% beat Bard, 65% beat DaVinci003, while being explicit about the limits, namely no new capabilities and brittle refusal behaviour.

### Self-Instruct: Aligning Language Models with Self-Generated Instructions（Wang et al., ACL 2023）

- **PDF**：[06_对齐_数据与偏好优化/Self-Instruct - Aligning Language Models with Self-Generated Instructions.pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/Self-Instruct - Aligning Language Models with Self-Generated Instructions.pdf>)
- **核心论点（中）**：指令微调的数据瓶颈可以用模型自己解决。从 175 条人工种子任务出发，让模型自动生成新任务、生成输入输出实例并过滤去重，即可自举出大规模指令训练集。
- **创新点（中）**：提出完全自动的指令与实例合成管线（约 52k 指令 / 82K 实例），无需人工标注；GPT-3 175B 经 Self-Instruct 训练后在 Super-NI 未见任务上从 25.7 提升到 39.9，接近 InstructGPT 的 40.8，明显优于原始 GPT-3。
- **Core thesis (EN)**: The instruction-data bottleneck can be bootstrapped by the model itself: starting from 175 human seed tasks, the model generates new tasks, then input/output instances, filtering and de-duplicating along the way.
- **Novelty (EN)**: A fully automatic synthesis pipeline producing about 52k instructions and 82K instances with no human labeling; Self-Instruct lifts GPT-3 175B from 25.7 to 39.9 on unseen Super-NI tasks, close to InstructGPT's 40.8 and well above vanilla GPT-3.

### WizardLM: Empowering Large Pre-Trained Language Models to Follow Complex Instructions（Xu et al., 2023）

- **PDF**：[06_对齐_数据与偏好优化/WizardLM - Empowering Large Pre-Trained Language Models to Follow Complex Instructions.pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/WizardLM - Empowering Large Pre-Trained Language Models to Follow Complex Instructions.pdf>)
- **核心论点（中）**：指令数据的"复杂度"比数量更关键。Evol-Instruct 让 LLM 对已有指令做迭代式改写演化（加约束、深化、具体化、合理化、引入不相关性问题），自动把训练分布推向更难的一侧。
- **创新点（中）**：首次把"指令进化"作为可复用的数据增强算子，并配以淘汰失败演化的回滚机制；基于 LLaMA 7B/13B 训练的 WizardLM 在人工与自动评估上超过 Alpaca、Vicuna，部分达到 ChatGPT 水平，且泛化到未见指令类型。
- **Core thesis (EN)**: Instruction complexity matters more than instruction count. Evol-Instruct has an LLM iteratively rewrite existing instructions (adding constraints, deepening, concretizing, reasoning steps, injecting irrelevance), automatically pushing the training distribution toward harder cases.
- **Novelty (EN)**: First treats instruction evolution as a reusable data-augmentation operator with rollback for failed evolutions; WizardLM (LLaMA 7B/13B) beats Alpaca and Vicuna on human and automatic evaluations, approaches ChatGPT on parts of the suite, and generalizes to unseen instruction types.

### AlpaGasus: Training a Better Alpaca with Fewer Data（Li et al., ICLR 2024）

- **PDF**：[06_对齐_数据与偏好优化/AlpaGasus - Training a Better Alpaca with Fewer Data.pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/AlpaGasus - Training a Better Alpaca with Fewer Data.pdf>)
- **核心论点（中）**：Alpaca 的 52K 数据里混入大量低质量样本，用全部数据反而拖累模型。用一个 GPT 打分器自动评估每条样本质量、只保留约 9K 条高质量数据即可。
- **创新点（中）**：用"数据质量过滤"而非"数据规模扩张"改善指令微调，7B 模型训练时间从 80 分钟降到 14 分钟（约 5.7 倍加速）；在人工与自动评估中，AlpaGasus 普遍优于原版 Alpaca，13B 版本在 Vicuna 基准上超过 ChatGPT 的 90%。
- **Core thesis (EN)**: Alpaca's 52K set contains many low-quality samples, so training on all of it hurts the model; an automatic GPT-based quality scorer that keeps roughly 9K high-quality instances is better.
- **Novelty (EN)**: Improves instruction tuning by quality filtering rather than scaling volume, cutting 7B training time from 80 to about 14 minutes (5.7x) and beating the original Alpaca across evaluations, with the 13B version exceeding 90% of ChatGPT on the Vicuna benchmark.

### Magpie: Alignment Data Synthesis from Scratch by Prompting Aligned LLMs with Nothing（Xu et al., NeurIPS 2024）

- **PDF**：[06_对齐_数据与偏好优化/Magpie - Alignment Data Synthesis from Scratch by Prompting Aligned LLMs with Nothing.pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/Magpie - Alignment Data Synthesis from Scratch by Prompting Aligned LLMs with Nothing.pdf>)
- **核心论点（中）**：不需要种子指令、不需要 GPT-4 蒸馏，也能得到大规模对齐数据。对齐模型内部已经编码了"用户会问什么"的先验：只喂给它聊天模板中"用户轮开始"的空前缀，模型就会自发生成五花八门的用户查询。
- **创新点（中）**：把数据合成简化为"零输入采样"，再配上检索式过滤与自评分配对，构成完全自足的对齐数据管线；Magpie-Air/Pro 仅花 206/614 GPU 小时即产出百万/千万级数据，不依赖人工标注也不依赖 GPT-4 API，并用长度控制胜率（LC win rate）修正评估偏差。
- **Core thesis (EN)**: Large-scale alignment data can be produced with neither seed instructions nor GPT-4 distillation, because aligned models already encode what users ask: feeding only the empty pre-query prefix of the chat template makes them spontaneously emit diverse user queries.
- **Novelty (EN)**: Reduces synthesis to zero-input sampling plus retrieval-based filtering and self-scored pairing, yielding a fully self-contained pipeline; Magpie-Air/Pro were built with 206/614 GPU hours with no human labels and no GPT-4 API, and length-controlled win rate is used to remove verbosity bias from evaluation.

### Textbooks Are All You Need（phi-1, Gunasekar et al., Microsoft, 2023）

- **PDF**：[06_对齐_数据与偏好优化/Textbooks Are All You Need (phi-1).pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/Textbooks Are All You Need (phi-1).pdf>)
- **核心论点（中）**：在小模型上，数据质量与数据构成的作用超过模型规模与训练时长。只用 6B 精选网页 token 加 1B 合成"教科书风格"数据训练 1.3B 模型，代码能力即可击败大得多的同类模型。
- **创新点（中）**：系统化的"课程式数据筛选"：分类器过滤低质网页、去重、再专门合成与真实代码同源但更干净的教科书式数据与 exercises；phi-1 在 8 张 A100 上训练 4 天即达 HumanEval 50.6%、MBPP 55.5%，超过 10 倍参数量的模型，350M 的 phi-1-small 仍达 45%。
- **Core thesis (EN)**: For small models, data quality and composition matter more than scale and training time. A 1.3B model trained on 6B filtered web tokens plus 1B synthetic textbook-style data reaches code-generation ability beyond much larger peers.
- **Novelty (EN)**: A curriculum of aggressive data curation (classifier filtering, deduplication, plus synthetic textbook-and-exercise data designed to be token-similar to real code) and a result on 8 A100s over 4 days: HumanEval 50.6% and MBPP 55.5% for phi-1, beating 10x-larger models, with the 350M phi-1-small still at 45%.


### LLaDA-Image: Building Strong Image Generators with Fully Open Training Recipes（Chuyan Chen, Haoxing Chen, Kun Chen et al., arXiv 2026）

- **PDF**：[06_对齐_数据与偏好优化/2609.03796v1-72a683f0.pdf](</home/kun/Desktop/paper/completed/06_对齐_数据与偏好优化/2609.03796v1-72a683f0.pdf>)
- **核心论点（中）**：LLaDA-Image 的核心论点是一个强图像生成器不必从大规模图文对开始，而可以先用真实图像自监督建立视觉先验，再逐步对齐语言、编辑指令和少步部署。论文展示 6B DiT、冻结 dLLM 理解模块、RQA–connector、真实数据主导课程、parameter-free RMSNorm/Muon 和 TwinFlow 蒸馏共同构成可检查、可复用的开放训练配方。
- **创新点（中）**：创新在于将 image-only 预训练/中训练、统一 dLLM 理解–生成–编辑、真实数据主导渐进训练和 TwinFlow 少步蒸馏整合到单一开源配方中。训练管线使用约 220M 样本，98% 为真实图像且 image-only 超过 90%，SFT 真实图像份额高于 70%；最终在 Qwen-Image-Bench 英文/中文达到 53.53/53.38 的开源 SOTA，并将 Turbo 推理压缩到 2–4 步。
- **Core thesis (EN)**: The paper argues that a strong image generator can be trained from scratch with a fully open recipe by first learning a visual prior from image-only data, then progressively aligning text and editing, and finally distilling to few-step inference.
- **Novelty (EN)**: LLaDA-Image combines a 6B single-stream DiT, a frozen LLaDA2.0-Mini dLLM understanding module with RQA and connector, real-data-dominant progressive training, parameter-free RMSNorm with Muon, and TwinFlow distillation. It uses about 220M generation samples, 98% real and more than 90% image-only, keeps real images above 70% in SFT, reaches Qwen-Image-Bench scores of 53.53 EN and 53.38 CN, and produces 2–4-step Turbo variants.
- **与我体系的关系**：与当前 Alignment, Data and Preference Optimization 分类相关：论文的主要贡献集中在开放训练配方、数据构造/过滤/字幕、图文对齐、指令编辑训练、混合任务 SFT、checkpoint merging、少步蒸馏和强化微调；它不是以偏好数据或人类反馈优化为核心，而是通过数据与训练流程实现生成模型对齐。
- **导入来源**：模型自动分类与结构化解读；保留原始 PDF，人工摘要可在后续复核中覆盖。
- **分类依据**：固定分类体系未专门覆盖图像生成模型训练配方。文本中与该类最接近的依据包括：论文 Scope 明确提到从 image-only visual-prior learning 到 language alignment、joint generation–editing 和 TwinFlow distillation 的训练路径，并记录 data construction、optimization choices 和 training schedule；附录 B 还出现 CoT Supervised Fine-tuning and Reinforcement Learning。因此低置信归入“对齐、数据与偏好优化”，但主贡献是多模态图像生成训练，需人工复核。

### 本节阅读顺序

InstructGPT → DPO → ORPO → Constitutional AI → LIMA → Self-Instruct / WizardLM / AlpaGasus / Magpie → phi-1。这一组与第 1、2 节共同构成微调安全的前提：对齐行为来自数据与目标函数，因此任何改变数据分布的训练（包括用户侧 LoRA 微调）都可能改写安全行为。

---

## 7. 参数高效微调

**主题定位**：微调接口之所以危险，是因为它便宜。这三篇定义了"便宜"的具体量级，也是 Safe LoRA 等防御的作用对象。

### LoRA: Low-Rank Adaptation of Large Language Models（Hu et al., ICLR 2022）

- **PDF**：[07_参数高效微调/LoRA - Low-Rank Adaptation of Large Language Models.pdf](</home/kun/Desktop/paper/completed/07_参数高效微调/LoRA - Low-Rank Adaptation of Large Language Models.pdf>)
- **核心论点（中）**：微调不需要更新全部权重。预训练大模型在任务适配时具有低"内在秩"，因此把权重更新约束为两个低秩矩阵的乘积并冻结原权重，就能以极小代价达到全量微调的效果。
- **创新点（中）**：可训练参数量比全量微调降低约 10000 倍、GPT-3 175B 的训练硬件计算需求降低 3 倍，显存与检查点体积同时崩塌式下降，且推理侧可把 BA 合并回 W 做到零额外延迟；这套设计使"人人可微调"成为现实，也直接构成了下游安全风险的入口。
- **Core thesis (EN)**: Fine-tuning does not require updating all weights, because adaptation to a downstream task has low intrinsic rank. Freezing the pretrained weights and expressing the update as a product of two low-rank matrices matches full fine-tuning at a fraction of the cost.
- **Novelty (EN)**: Roughly 10,000x fewer trainable parameters and 3x less compute hardware for GPT-3 175B, with checkpoints small enough to distribute and no inference latency since BA merges back into W; this economy is exactly what opens the fine-tuning threat surface studied in sections 1-2.

### QLoRA: Efficient Finetuning of Quantized LLMs（Dettmers et al., NeurIPS 2023）

- **PDF**：[07_参数高效微调/QLoRA - Efficient Finetuning of Quantized LLMs.pdf](</home/kun/Desktop/paper/completed/07_参数高效微调/QLoRA - Efficient Finetuning of Quantized LLMs.pdf>)
- **核心论点（中）**：量化会损伤性能这一担忧在微调场景下并不成立：把基座权重压到 4-bit 后在其上挂 LoRA 适配器，微调效果与 16-bit 全量微调一致，从而把 65B 模型塞进单张 48GB GPU。
- **创新点（中）**：三件套构成可复用的 4-bit 微调基础设施：NF4（信息论最优的正态浮点数据类型）、Double Quantization（把量化常数本身再量化，每参数再省约 0.37 bit）、Paged Optimizers（用 CPU 内存峰值兜底避免 OOM）；据此训出当时最好的开源对话模型 Guanaco，单卡 24 小时达到 ChatGPT 在 Vicuna 基准上 90%+ 的水平（论文报告 99.3%），并开源 8 个数据集、1,000 余个模型。
- **Core thesis (EN)**: The worry that quantization costs accuracy does not hold for fine-tuning: with base weights in 4-bit and LoRA adapters on top, quality matches 16-bit full fine-tuning, letting a 65B model be tuned on a single 48GB GPU.
- **Novelty (EN)**: Ships reusable 4-bit infrastructure, namely NF4 (information-theoretically optimal data type for normally distributed weights), Double Quantization (quantizing the quantization constants themselves, saving about 0.37 bit per parameter) and Paged Optimizers (CPU-memory spillover to survive activation peaks); the recipe yields Guanaco, at 24 hours on one GPU reaching about 99.3% of ChatGPT on Vicuna, and releases 8 datasets and over 1,000 models.

### DoRA: Weight-Decomposed Low-Rank Adaptation（Liu et al., ICML 2024）

- **PDF**：[07_参数高效微调/DoRA - Weight-Decomposed Low-Rank Adaptation.pdf](</home/kun/Desktop/paper/completed/07_参数高效微调/DoRA - Weight-Decomposed Low-Rank Adaptation.pdf>)
- **核心论点（中）**：LoRA 之所以有效是因为它部分改变了预训练权重，但它把"学习率方向"与"更新方向"耦合在一起，两者都需要不同的优化性质。DoRA 把权重分解为幅度与方向两部分，只让方向走低秩更新。
- **创新点（中）**：受全量微调中"权重变化主要来自方向而非幅度"的观察启发，DoRA 用一个向量专门学幅度、用 LoRA 专门学方向，从而在同等参数预算下显著提升学习能力的接近程度；在 LLaMA-2 文本、LLaVA 多模态、VL-BART 图像描述上一致优于 LoRA，且推理时可合并、零额外开销。
- **Core thesis (EN)**: LoRA works because it partially changes pretrained weights, but it entangles the magnitude and direction of that change, which call for different optimization treatment. DoRA decomposes the weight into magnitude and direction and routes only the direction through the low-rank update.
- **Novelty (EN)**: Motivated by the observation that full fine-tuning changes weight direction far more than magnitude, DoRA learns magnitude with a dedicated vector while LoRA handles direction, beating LoRA at equal parameter budget on LLaMA-2, LLaVA and VL-BART while merging at inference with no extra overhead.

---

## 8. 推理与思维链

**主题定位**：推理能力从何而来、如何被测量、以及"多想一会儿"值多少算力。安全相关点在于：思维链是外化可审计的推理，也是可被污染的对象。

### Chain-of-Thought Prompting Elicits Reasoning in Large Language Models（Wei et al., NeurIPS 2022）

- **PDF**：[08_推理与思维链/Chain-of-Thought Prompting Elicits Reasoning in Large Language Models.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/Chain-of-Thought Prompting Elicits Reasoning in Large Language Models.pdf>)
- **核心论点（中）**：把中间推理步骤显式写进少样本示例，模型就会照做，从而在算术、常识与符号推理上大幅提升。关键不在示例内容本身，而在于"生成长思考链"这一输出格式。
- **创新点（中）**：证明 CoT 是规模涌现能力：小模型加 CoT 无效，超过约几十 B 参数量才突然起效；PaLM 540B 加 8 个 CoT 样例在 GSM8K 数学词题上取得当时最高准确率（甚至超过带验证器的多任务微调 GPT-3），仅需把标准 prompt 换成带推理链的 prompt。
- **Core thesis (EN)**: Writing intermediate reasoning steps into few-shot exemplars makes the model imitate them, sharply improving arithmetic, commonsense and symbolic reasoning. The mechanism is the long chain-of-thought output format itself rather than the exemplars' content.
- **Novelty (EN)**: Establishes CoT as an emergent ability of scale, ineffective in small models and suddenly effective past roughly tens of billions of parameters; PaLM 540B with 8 exemplars reaches a new state of the art on GSM8K, surpassing even finetuned GPT-3 with a verifier purely by changing the prompt format.

### Tree of Thoughts: Deliberate Problem Solving with Large Language Models（Yao et al., NeurIPS 2023）

- **PDF**：[08_推理与思维链/Tree of Thoughts - Deliberate Problem Solving with Large Language Models.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/Tree of Thoughts - Deliberate Problem Solving with Large Language Models.pdf>)
- **核心论点（中）**：CoT 把推理压成单条直线采样，无法回溯与比较。ToT 把问题分解成可评估的"思维"单元，在状态树上做 BFS/DFS 式搜索，由模型自己给中间状态打分并决定保留、回溯或扩展。
- **创新点（中）**：第一次把经典搜索（广度/深度优先、剪枝、自评估启发式）嫁接到语言模型的推理过程上，实现"深思熟虑"式问题求解；在 Game of 24 上 GPT-4 的成功率从 CoT 的 4% 提升到 74%，并在创意写作与迷你填数问题上同样领先。
- **Core thesis (EN)**: CoT reduces reasoning to a single straight-line sampling pass that cannot backtrack or compare alternatives. ToT decomposes problems into evaluatable "thought" units and searches a tree with BFS/DFS, using the model's own self-evaluation of intermediate states to keep, prune or expand.
- **Novelty (EN)**: First grafting of classical search (breadth/depth-first, pruning, self-scored heuristics) onto LLM reasoning, enabling deliberate problem solving; success on Game of 24 rises from 4% with CoT to 74% with GPT-4, with similar gains on creative writing and a mini cross-sum puzzle.

### Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models（Wang et al., ACL 2023）

- **PDF**：[08_推理与思维链/Plan-and-Solve Prompting - Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/Plan-and-Solve Prompting - Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models.pdf>)
- **核心论点（中）**：Zero-shot-CoT（"让我们一步步想"）失败在两个地方：模型没有先理解全题就顺着说下去，以及执行步骤时常丢失任务意图。PS-Prompt 显式要求模型先制定计划、再按计划分步执行。
- **创新点（中）**：零样本、无需示例即可稳定优于 CoT 与 Zero-shot-CoT，平均比 Zero-shot-CoT 高 2.5%；并给出 PS+ 变体在 GSM8K 上取得 76.7%，接近人工设计思维链的 77.6% 并超过自动生成的 75.9%；同时缓解算术问题中的数字重排序与计算遗漏。
- **Core thesis (EN)**: Zero-shot-CoT fails because the model does not first grasp the whole problem before riffing step by step, and because it loses task intent while executing. PS-Prompt asks the model to devise a plan up front and then carry it out stepwise.
- **Novelty (EN)**: Zero-shot with no exemplars yet consistently better than CoT and Zero-shot-CoT (average 2.5% over Zero-shot-CoT); the PS+ variant reaches 76.7% on GSM8K, close to manually written chains at 77.6% and above auto-generated chains at 75.9%, while reducing digit reordering and missed computations.

### Towards Understanding Chain-of-Thought Prompting: An Empirical Study of What Matters（Suzgun et al., 2023）

- **PDF**：[08_推理与思维链/Towards Understanding Chain-of-Thought Prompting - An Empirical Study of What Matters.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/Towards Understanding Chain-of-Thought Prompting - An Empirical Study of What Matters.pdf>)
- **核心论点（中）**：CoT 有效的原因长期停留在"直觉"层面。本文用受控实验把提示分解成若干因素（相关性、推理正确性、步骤顺序、语法、问题多样性、指令措辞、推理链长度），逐一量化其贡献。
- **创新点（中）**：给出可操作的结论：与问题"语义相关"且"推理步骤顺序正确"是最重要的两个因素，错误步骤的破坏性远大于随机占位符；同时澄清若干误导直觉（例如链更长不一定更好、模板换词影响很小），把 CoT 从玄学变成可设计对象。
- **Core thesis (EN)**: CoT's effectiveness had been explained mostly by intuition. This work decomposes the prompt into controlled factors, namely relevance, correctness of reasoning, step ordering, syntax, question diversity, instruction wording and chain length, and measures each one's contribution.
- **Novelty (EN)**: Delivers actionable findings, chiefly that semantic relevance to the question and correct ordering of reasoning steps dominate, and that wrong steps hurt far more than placeholders; it also dispels misleading intuitions (longer chains are not automatically better, template wording barely matters), making CoT a designable object instead of folklore.

### Quiet-STaR: Language Models Can Teach Themselves to Think Before Speaking（Zelikman et al., 2024）

- **PDF**：[08_推理与思维链/Quiet-STaR - Language Models Can Teach Themselves to Think Before Speaking.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/Quiet-STaR - Language Models Can Teach Themselves to Think Before Speaking.pdf>)
- **核心论点（中）**：思维链不必等到被提示才出现。Quiet-STaR 让模型在每个 token 位置先生成内部理由（rationale），再用它预测下一个 token，并通过可微的混合器以"是否有助于正确预测"作为自监督信号学会思考。
- **创新点（中）**：把推理从"输出层的显式链"移到"每个 token 的内部潜变量"，在继续预训练后即可零样本提升：GSM8K 零样本准确率从 5.9% 提到 10.9%、CommonsenseQA 从 36.3% 提到 47.2%，且无需任何任务微调；理由本身可作为可解释的中间产物被检查。
- **Core thesis (EN)**: Reasoning should not wait for a prompt. Quiet-STaR has the model generate an internal rationale at every token position, use it to predict the next token, and learn to think self-supervisedly from whether that prediction improved, via a differentiable mixer.
- **Novelty (EN)**: Moves chain-of-thought from an explicit output-level sequence to a per-token latent variable, improving zero-shot accuracy after continued pretraining: GSM8K 5.9% to 10.9% and CommonsenseQA 36.3% to 47.2% with no task-specific fine-tuning, while the generated rationales make the thinking process inspectable.

### Let's Verify Step by Step（Lightman et al., OpenAI, ICLR 2024）

- **PDF**：[08_推理与思维链/Let%27s Verify Step by Step.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/Let%27s Verify Step by Step.pdf>)
- **核心论点（中）**：解决"结果正确但过程错误"的问题需要逐步监督而非结果监督。过程奖励模型（PRM）对推理链的每一步单独打分，能捕捉到只有最终答案监督会放过的中间错误。
- **创新点（中）**：人工标注 MATH 解答的每一步并开源 PRM800K（800K 条步级标签、覆盖约 75K 条解答）；在 MATH 子集上过程监督模型准确率达 78%，显著高于结果监督基线，并显著减少"答案蒙对但中间步错"的比例；确立 PRM 作为测试时搜索的可验证 critic。
- **Core thesis (EN)**: Cases where the answer is right but the reasoning is wrong require process supervision rather than outcome supervision. A process reward model scores each reasoning step, catching intermediate errors that outcome-only supervision misses.
- **Novelty (EN)**: Releases PRM800K, 800K human step-level labels over about 75K solutions; process supervision reaches 78% on a MATH subset, materially above the outcome-supervision baseline and with far fewer lucky-but-wrong solutions, establishing PRMs as the verifiable critic for test-time search.

### Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Model Parameters（Snell et al., 2024）

- **PDF**：[08_推理与思维链/Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters.pdf>)
- **核心论点（中）**：增加推理时算力与增加模型参数是两条可以互相替代的缩放路线，但必须先学会把算力分配给"难题目"。用过程奖励模型估计每道题的难度并据此选择搜索宽度与修订轮数，即可接近该算力下的最优性能。
- **创新点（中）**：提出按 prompt 难度的计算最优分配策略，相同推理算力下比 best-of-N 采样效率提升 4 倍以上；在 FLOPs 对齐的比较中，小模型加更多测试时算力常常超过大得多的基座模型，并明确指出这一结论只在有可验证 reward / 便宜 critic 的前提下成立。
- **Core thesis (EN)**: Test-time compute and parameter count are substitutable scaling axes, provided compute is routed to hard problems. Estimating per-prompt difficulty with a process reward model and then choosing search width and revision rounds approaches optimal performance under a fixed budget.
- **Novelty (EN)**: Introduces compute-optimal per-prompt allocation, giving over 4x better efficiency than best-of-N at equal inference compute, and shows that in a FLOPs-matched comparison a small model with more test-time compute can beat a far larger base model, while flagging that this only holds when a verifier or cheap critic exists.

### Faith and Fate: Limits of Transformers on Compositionality（Kim et al., NeurIPS 2023）

- **PDF**：[08_推理与思维链/Faith and Fate - Limits of Transformers on Compositionality.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/Faith and Fate - Limits of Transformers on Compositionality.pdf>)
- **核心论点（中）**：Transformer 处理组合任务的方式像"忠实但易迷路的水手"：它能可靠地局部跟随图结构推理，但小误差会沿深度与宽度累积放大，最终整体崩溃。这是架构层面的限制，不是数据不够。
- **创新点（中）**：用两个合成基准（GSM-Hard 类算术图与几何面积推理）把问题显式参数化为计算图，定量给出准确率随图深度/宽度的陡降曲线，并证明这种退化在更大模型、更多数据、各种提示技巧下依然存在，为"多步推理不可无限信任"提供了机理证据。
- **Core thesis (EN)**: Transformers approach compositional tasks like faithful sailors: they locally track the graph structure of a problem but small errors compound with depth and width until performance collapses. The limit is architectural, not a data shortage.
- **Novelty (EN)**: Parameterizes problems as explicit computation graphs on synthetic benchmarks (GSM-Hard-style arithmetic and geometric area reasoning), quantifies the sharp accuracy decline with graph depth and width, and shows the degradation persists with larger models, more data and prompting tricks, giving mechanistic evidence that multi-step reasoning cannot be trusted without bound.

### Large Language Models Cannot Self-Correct Reasoning Yet（Huang et al., ICLR 2024）

- **PDF**：[08_推理与思维链/Large Language Models Cannot Self-Correct Reasoning Yet.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/Large Language Models Cannot Self-Correct Reasoning Yet.pdf>)
- **核心论点（中）**：此前声称"自我纠错有效"的工作几乎都悄悄借用了 oracle 标签（知道标准答案才判断是否要改）。去掉这个作弊信号后，模型在无外部反馈的自我反思下反而会让正确答案变错，多轮自我修正平均降低推理准确率。
- **创新点（中）**：严格区分"内在自我纠错"（无外部反馈）与"带 oracle 的纠错"，用 CommonSenseQA、GSM8K 等基准给出一致的反例，并要求以后评估自我纠错必须报告无 oracle 设定，成为该方向的评测纠偏论文。
- **Core thesis (EN)**: Earlier self-correction success nearly always smuggled in oracle labels, checking against ground truth to decide whether to revise. Remove that cheat signal and intrinsic self-correction flips right answers to wrong, reducing reasoning accuracy over rounds.
- **Novelty (EN)**: Separates intrinsic self-correction from oracle-guided correction and shows consistent counterexamples on CommonSenseQA and GSM8K, arguing that any self-correction claim must report the no-oracle setting; a corrective intervention for the test-time-improvement literature.

### DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning（DeepSeek-AI, 2025）

- **PDF**：[08_推理与思维链/DeepSeek-R1 - Incentivizing Reasoning Capability in LLMs via Reinforcement Learning.pdf](</home/kun/Desktop/paper/completed/08_推理与思维链/DeepSeek-R1 - Incentivizing Reasoning Capability in LLMs via Reinforcement Learning.pdf>)
- **核心论点（中）**：推理能力可以不必用人类示范轨迹教出来。从 DeepSeek-V3-Base 出发、只用基于规则的可验证奖励做纯强化学习（跳过 SFT），模型的自我反思、验证与动态调整策略等行为会自发涌现（R1-Zero），并在数学、竞赛编程等可验证任务上超越监督学习基线。
- **创新点（中）**：给出"纯 RL 激发推理"的强证据：GRPO 仅以最终答案正确性为奖励，AIME 2024 pass@1 随训练自然攀升，R1 最终达 79.8%；同时解决 R1-Zero 可读性差与语言混杂问题（多阶段冷启动、拒绝采样、SFT 与 RL 组合）；并证明大模型涌现出的长思维链可蒸馏到 1.5B–70B 小模型（用 800K 样本微调 2–3 轮），显著降低小模型获得推理能力的门槛。
- **Core thesis (EN)**: Reasoning need not be imitated from human demonstrations. Starting from DeepSeek-V3-Base and applying pure RL with rule-based verifiable rewards while skipping SFT, self-reflection, verification and dynamic strategy adaptation emerge on their own (R1-Zero), beating supervised baselines on mathematics and competition coding.
- **Novelty (EN)**: Provides strong evidence that RL alone elicits reasoning, training with GRPO on final-answer correctness only and watching AIME 2024 pass@1 climb during RL to 79.8% for R1; fixes R1-Zero's poor readability and language mixing through a multi-stage cold-start, rejection-sampling, SFT and RL pipeline; and shows emergent long chains can be distilled into 1.5B-70B models from 800K samples over 2-3 epochs, sharply lowering the entry cost for small reasoning models.

---

## 9. 规划与 LLM-Modulo

**主题定位**：LLM 能不能做规划？这一组的结论是否定的（能力上不可自验证），并给出正确姿势：LLM 生成 + 外部 critic/求解器验证。这直接支撑第 4 组智能体安全的可信执行设计。

### On the Planning Abilities of Large Language Models: A Critical Investigation（Valmeekam et al., NeurIPS 2023）

- **PDF**：[09_规划与LLM-Modulo/On the Planning Abilities of Large Language Models (A Critical Investigation with a Proposed Benchmark).pdf](</home/kun/Desktop/paper/completed/09_规划与LLM-Modulo/On the Planning Abilities of Large Language Models (A Critical Investigation with a Proposed Benchmark).pdf>)
- **核心论点（中）**：把 Blocksworld 等经典规划问题直接交给 LLM 自主生成完整计划，成功率接近于零（约 3%）。此前正面结论主要来自"只需验证给定计划"或"人类在环"的设定，而非模型真的会规划。
- **创新点（中）**：用可组合、可控难度的经典规划基准区分"验证任务"与"生成任务"，量化了模型能判断计划对不对、却生成不出正确计划的鸿沟；并指出增加 CoT、多次采样、微调几乎无改善，为后面的 LLM-Modulo 立场提供实证基础。
- **Core thesis (EN)**: Asking LLMs to generate full plans for classic domains such as Blocksworld autonomously yields near-zero success (roughly 3%). Positive prior results came from verification-style tasks or human-in-the-loop settings, not from genuine planning ability.
- **Novelty (EN)**: Separates plan verification from plan generation on a compositional, difficulty-controlled benchmark and quantifies the gap, showing that CoT, more samples and fine-tuning barely help, which grounds the LLM-Modulo position that follows.

### Position: LLMs Can't Plan, But Can Help Planning in LLM-Modulo Frameworks（Kambharka et al., arXiv:2402.01817, ICML 2024 position）

- **PDF**：[09_规划与LLM-Modulo/Position - LLMs Can%27t Plan, But Can Help Planning in LLM-Modulo Frameworks.pdf](</home/kun/Desktop/paper/completed/09_规划与LLM-Modulo/Position - LLMs Can%27t Plan, But Can Help Planning in LLM-Modulo Frameworks.pdf>)
- **核心论点（中）**：LLM 本质是一个快速的近似模式一系统，无法自我验证所生成计划的正确性，因此在结构上不能作为规划器。正确的架构是让 LLM 充当生成器，把"对不对"交给外部 critic（求解器、验证器、人类）判定。
- **创新点（中）**：形式化提出 LLM-Modulo 框架（生成器与 critic 双向迭代、以任务无关的约束满足为目标），给出与 Search-based、ReAct 类方法的分类对比，并指明关键开放问题不是提示技巧而是如何设计合适的 critic；本文是"智能体可信执行"方向的纲领性文献。
- **Core thesis (EN)**: LLMs behave like a fast approximate System-1 and cannot self-verify the plans they emit, so structurally they cannot be planners. The right architecture casts the LLM as generator and delegates correctness to an external critic such as a solver, verifier or human.
- **Novelty (EN)**: Formalizes the LLM-Modulo framework with generator-critic iteration aimed at task-agnostic constraint satisfaction, classifies it against search-based and ReAct-style approaches, and identifies critic design, not prompt engineering, as the open problem; a programmatic reference for trustworthy agent execution.

### LLM+P: Empowering Large Language Models with Optimal Planning Proficiency（Liu et al., 2023）

- **PDF**：[09_规划与LLM-Modulo/LLM+P - Empowering Large Language Models with Optimal Planning Proficiency.pdf](</home/kun/Desktop/paper/completed/09_规划与LLM-Modulo/LLM+P - Empowering Large Language Models with Optimal Planning Proficiency.pdf>)
- **核心论点（中）**：分工即可解决规划的可靠性问题：LLM 负责把自然语言问题翻译成 PDDL 领域与问题描述，经典规划器负责求解并保证最优性，LLM 再把符号计划翻译回自然语言。
- **创新点（中）**：用"LLM 翻译 + Fast Downward 求解"的两段式管线在 Blocksworld、Mystery Blocksworld 等基准上大幅超越纯 LLM 基线（如 SayCan），后者因只有 3 个可选动作而虚高到约 90%；确立 PDDL 作为 LLM 与经典规划器之间接口的可行性。
- **Core thesis (EN)**: Division of labour settles plan reliability: the LLM translates the natural-language problem into a PDDL domain and problem, a classical planner solves it with optimality guarantees, and the LLM translates the symbolic plan back into language.
- **Novelty (EN)**: A two-stage LLM-translation plus Fast Downward pipeline that far exceeds pure-LLM baselines on Blocksworld and Mystery Blocksworld, where SayCan is inflated to about 90% by having only three candidate actions, and validates PDDL as the interface between LLMs and classical planners.

### Classical Planning with LLM-Generated Heuristics: Challenging the State of the Art with Python Code（Corrêa et al., NeurIPS 2025）

- **PDF**：[09_规划与LLM-Modulo/Classical Planning with LLM-Generated Heuristics - Challenging the State of the Art with Python Code.pdf](</home/kun/Desktop/paper/completed/09_规划与LLM-Modulo/Classical Planning with LLM-Generated Heuristics - Challenging the State of the Art with Python Code.pdf>)
- **核心论点（中）**：LLM 不必自己规划，它可以写"如何规划"的代码。让 LLM 按领域描述自动生成启发式函数（以 Python 实现），交给贪心最佳优先搜索使用，即可在经典规划上达到甚至超过领域无关的 SOTA 启发式。
- **创新点（中）**：把 LLM 从"计划生成器"换成"启发式生成器"，在 Pyperplan 上实现并参加 IPC 2023 学习赛道；核心证据是在训练分布外（新领域、新实例）优于端到端 LLM 规划，因为启发式是可验证、可组合的抽象，而计划是一次性输出。
- **Core thesis (EN)**: Instead of planning, the LLM can write the code for how to plan: it synthesizes domain heuristics in Python from the domain description, which greedy best-first search then consumes, matching or beating state-of-the-art domain-independent heuristics.
- **Novelty (EN)**: Swaps the LLM's role from plan generator to heuristic generator, implemented on Pyperplan and entered in the IPC 2023 Learning Track, with the key result that it beats end-to-end LLM planning out of distribution because heuristics are verifiable reusable abstractions while plans are one-off outputs.

### SafeRun: Enabling Determinism in LLM Planning for Running（2026）

- **PDF**：[09_规划与LLM-Modulo/SafeRun - Enabling Determinism in LLM Planning for Running.pdf](</home/kun/Desktop/paper/completed/09_规划与LLM-Modulo/SafeRun - Enabling Determinism in LLM Planning for Running.pdf>)
- **核心论点（中）**：跑步训练这类有硬安全约束（强度、恢复、伤病风险）的任务不能容忍 LLM 的随机性。SafeRun 把"理解用户目标"交给 LLM，把"生成并校验可行计划"交给约束求解器，二者解耦后安全成为结构保证而非概率结果。
- **创新点（中）**：给出 LLM-interpret / solver-enforce 的具体分工接口，在 5 个 LLM 上评测安全约束满足率达 100%，而纯 prompt 工程（PE）平均仅 79.1%、CodeAct 平均 97.6%；同时保留 LLM 处理自然语言偏好的能力，是 LLM-Modulo 思想在真实约束场景的实证落地。
- **Core thesis (EN)**: Domains with hard safety constraints like running training cannot tolerate LLM stochasticity. SafeRun hands goal interpretation to the LLM and plan generation plus validation to a constraint solver, making safety a structural guarantee instead of a probabilistic outcome.
- **Novelty (EN)**: Specifies the LLM-interpret / solver-enforce interface and reports 100% constraint satisfaction across five LLMs versus 79.1% average for prompt engineering and 97.6% for CodeAct, keeping natural-language preference handling while empirically landing the LLM-Modulo idea in a constrained real-world task.

### Say'n'Fly: An LLM-Modulo Online Planning Framework to Automate UAV Command and Control（RO-MAN 2025）

- **PDF**：[09_规划与LLM-Modulo/Say%27n%27Fly - An LLM-Modulo Online Planning Framework to Automate UAV Command and Control.pdf](</home/kun/Desktop/paper/completed/09_规划与LLM-Modulo/Say%27n%27Fly - An LLM-Modulo Online Planning Framework to Automate UAV Command and Control.pdf>)
- **核心论点（中）**：无人机指挥需要把自然语言任务意图转成在线可执行计划，而飞控约束不可违反。Say'n'Fly 用 LLM-Modulo 架构把候选动作交给可行性检查后再进入规划，从机制上剪掉不可执行动作。
- **创新点（中）**：将 LLM-Modulo 从离线基准拓展到在线、动态环境中的 UAV 指挥控制，以不可行动作剪枝作为 critic 的具体形态；在搜索与救援场景中的规划效率比现有框架高 70%，同时显著降低无效或危险动作。
- **Core thesis (EN)**: UAV command needs natural-language intent turned into an online executable plan under non-negotiable flight constraints. Say'n'Fly uses an LLM-Modulo architecture where candidate actions pass a feasibility check before entering the plan, structurally pruning infeasible ones.
- **Novelty (EN)**: Extends LLM-Modulo from offline benchmarks to online planning for UAV command and control, with infeasible-action pruning as the concrete critic, reporting 70% higher planning efficiency than existing frameworks in search-and-rescue while cutting invalid or unsafe actions.

---

## 10. 智能体与工具使用

**主题定位**：智能体的能力基座：推理-行动耦合、反思、工具 API 学习、环境基准。与第 4 组构成"能力/风险"两面。

### ReAct: Synergizing Reasoning and Acting in Language Models（Yao et al., ICLR 2023）

- **PDF**：[10_智能体与工具使用/ReAct - Synergizing Reasoning and Acting in Language Models.pdf](</home/kun/Desktop/paper/completed/10_智能体与工具使用/ReAct - Synergizing Reasoning and Acting in Language Models.pdf>)
- **核心论点（中）**：纯推理（CoT）会与外部世界断联、产生幻觉；纯行动（动作策略）缺乏高层规划。把思考轨迹与动作/观察交替成同一条轨迹，推理指导动作选择、动作结果修正推理。
- **创新点（中）**：首次以统一提示格式实现推理与工具调用的交替，在 HotpotQA/Fever 上超越 CoT 与动作-only 基线，在 ALFWorld 上相对基线绝对提升 34%、WebShop 提升 10%；同时提升可解释性与可信度，奠定此后所有 agent 循环的原型。
- **Core thesis (EN)**: Pure reasoning (CoT) loses contact with the world and hallucinates, while pure acting lacks high-level planning. Interleaving thoughts with actions and observations in one trajectory lets reasoning steer action selection and lets action results correct reasoning.
- **Novelty (EN)**: First realization of an interleaved reason-act loop in a single prompt format, beating CoT and acting-only baselines on HotpotQA and Fever and gaining 34% and 10% absolute on ALFWorld and WebShop, while improving interpretability and trustworthiness and becoming the prototype for every agent loop since.

### Reflexion: Language Agents with Verbal Reinforcement Learning（Shinn et al., NeurIPS 2023）

- **PDF**：[10_智能体与工具使用/Reflexion - Language Agents with Verbal Reinforcement Learning.pdf](</home/kun/Desktop/paper/completed/10_智能体与工具使用/Reflexion - Language Agents with Verbal Reinforcement Learning.pdf>)
- **核心论点（中）**：智能体不必靠更新权重来学习。把失败信号转成自然语言自我反思并写入情景记忆，下次尝试时把反思读回提示，即可实现一种"语义梯度下降"。
- **创新点（中）**：用语言反馈替代标量奖励，避开 RL 对样本效率与长时序稀疏奖励的敏感问题，在编程、决策、推理任务一致提升；HumanEval 达 91% pass@1，超过 GPT-4 的 80%，成为无训练智能体改进的标准范式。
- **Core thesis (EN)**: Agents can improve without touching weights. Converting failure signals into verbal self-reflections stored in episodic memory and replaying them into the prompt on the next attempt acts like gradient descent in natural language.
- **Novelty (EN)**: Substitutes language feedback for scalar rewards, sidestepping sample-efficiency and long-horizon sparse-reward problems, improving coding, decision-making and reasoning tasks and reaching 91% pass@1 on HumanEval versus GPT-4's 80%; the standard recipe for training-free agent improvement.

### Toolformer: Language Models Can Teach Themselves to Use Tools（Schick et al., NeurIPS 2023）

- **PDF**：[10_智能体与工具使用/Toolformer - Language Models Can Teach Themselves to Use Tools.pdf](</home/kun/Desktop/paper/completed/10_智能体与工具使用/Toolformer - Language Models Can Teach Themselves to Use Tools.pdf>)
- **核心论点（中）**：使用工具不需要人工标注。模型自监督地判断"在这里插一个 API 调用是否能降低后续困惑度"，只保留有用的调用样本进行微调，就学会何时调、调什么、怎么用返回值。
- **创新点（中）**：用"预测增益"作为自动筛选准则，把少量示范即得到数千训练样本；在计算器、搜索、翻译、问答、日历 API 上显著改善零样本表现，且推理时仍由模型自主决定是否调工具；确立自监督工具学习范式。
- **Core thesis (EN)**: Tool use needs no hand labels: the model self-supervisedly decides whether inserting an API call at a position lowers future perplexity, keeps only useful calls as training data, and thereby learns when to call, what to call and how to use the result.
- **Novelty (EN)**: Uses predicted perplexity gain as an automatic filtering criterion, turning a handful of demonstrations into thousands of training samples; improves zero-shot performance across calculator, search, translation, QA and calendar APIs while keeping the call decision model-driven at inference, establishing self-supervised tool learning.

### ToolLLM: Facilitating Large Language Models to Master 16000+ Real-World APIs（Qin et al., ICLR 2024）

- **PDF**：[10_智能体与工具使用/ToolLLM - Facilitating Large Language Models to Master 16000+ Real-World APIs.pdf](</home/kun/Desktop/paper/completed/10_智能体与工具使用/ToolLLM - Facilitating Large Language Models to Master 16000+ Real-World APIs.pdf>)
- **核心论点（中）**：真实工具使用的难点不是调用单个 API，而是上万个 API 的检索、单工具与多工具协同、以及复杂指令分解。ToolLLM 把规模化 API 语料、训练管线与评测器一起建起来。
- **创新点（中）**：从 RapidAPI 构建覆盖 16000+ 真实 API 的 ToolBench 指令集（单工具/多工具/并行），用 DFSDT（深度优先决策树）多轮探索替代线性思考提升复杂规划成功率；ToolLLaMA 在自动与人工评测上接近 ChatGPT，且保持 API 检索器与工具使用的耦合。
- **Core thesis (EN)**: Real tool use is hard not because of one API call but because of retrieving among tens of thousands, coordinating single and multi-tool calls and decomposing complex instructions. ToolLLM builds the corpus, training pipeline and evaluator at that scale together.
- **Novelty (EN)**: Constructs ToolBench instructions over 16,000+ real RapidAPI endpoints (single-tool, multi-tool, parallel), introduces DFSDT depth-first decision-tree exploration for harder planning instead of linear thinking, and shows ToolLLaMA approaching ChatGPT on both automatic and human evaluation with retriever-tool use kept coupled.

### ToolQA: A Dataset for LLM Question Answering with External Tools（Zhuang et al., NeurIPS 2024 D&B）

- **PDF**：[10_智能体与工具使用/ToolQA - A Dataset for LLM Question Answering with External Tools.pdf](</home/kun/Desktop/paper/completed/10_智能体与工具使用/ToolQA - A Dataset for LLM Question Answering with External Tools.pdf>)
- **核心论点（中）**：现有工具使用基准之所以被纯推理刷榜，是因为答案本身就在模型内部知识里。ToolQA 用 13 个专用工具与真实数据库表格构造问题，使其与参数化知识重叠最小，强制模型必须调用工具。
- **创新点（中）**：以"低重叠"为设计目标的数据集，覆盖数据库查询、计算器、天气、股价、日程等；系统评测 ReAct 与 PAL/PoT 等程序化路线，揭示其在多步数值聚合与工具选择上的失效模式，并给出改进方向。
- **Core thesis (EN)**: Existing tool-use benchmarks get saturated by pure reasoning because the answers already sit in parametric knowledge. ToolQA builds questions over 13 dedicated tools and real database tables that minimally overlap with internal knowledge, forcing tool calls.
- **Novelty (EN)**: A dataset designed around low parametric overlap spanning database queries, calculator, weather, stock and scheduling; it evaluates ReAct alongside PAL/PoT-style program-aided routes, exposing failure modes in multi-step numeric aggregation and tool selection and pointing to concrete improvements.

### WebGPT: Browser-assisted Question-answering with Human Feedback（Nakano et al., 2022）

- **PDF**：[10_智能体与工具使用/WebGPT - Browser-assisted Question-answering with Human Feedback.pdf](</home/kun/Desktop/paper/completed/10_智能体与工具使用/WebGPT - Browser-assisted Question-answering with Human Feedback.pdf>)
- **核心论点（中）**：长时效、需要引用外部信息的问题应交给能浏览网页的模型回答。WebGPT 通过人类反馈学习浏览动作序列，最终输出带引用的答案。
- **创新点（中）**：第一个把 GPT-3 与真实浏览器交互（搜索、点击、摘录、滚动）结合并用 RLHF 训练的智能体；人评偏好率比人类演示高 56%、比 Reddit 最佳回答高 69%；同时早期记录了浏览智能体的安全失效模式（劫持、误导网站），为第 4 组提示注入研究埋下伏笔。
- **Core thesis (EN)**: Long-horizon questions needing external information belong to a model that can browse. WebGPT learns a sequence of browser actions from human feedback and answers with citations.
- **Novelty (EN)**: The first GPT-3 agent coupled to a live browser (search, click, quote, scroll) trained with RLHF, preferred over human demonstrators 56% of the time and over top Reddit answers 69%, and an early record of web-agent safety failure modes such as hijacking and misleading sites that foreshadow the prompt-injection literature in section 4.

### WebArena: A Realistic Web Environment for Building Autonomous Agents（Zhou et al., ICLR 2024）

- **PDF**：[10_智能体与工具使用/WebArena - A Realistic Web Environment for Building Autonomous Agents.pdf](</home/kun/Desktop/paper/completed/10_智能体与工具使用/WebArena - A Realistic Web Environment for Building Autonomous Agents.pdf>)
- **核心论点（中）**：现有网页智能体基准过于简化（观测为可执行代码、任务短且单一），无法反映真实网站。WebArena 提供功能自洽、可复现的网站生态（电商、论坛、GitLab、地图、知识库）供智能体端到端完成任务。
- **创新点（中）**：812 个有确定成败判据的自然语言任务，并给出函数式评估而非文本相似度打分；最强 GPT-4 智能体成功率仅 14.41%，而人类为 78.24%，量化出巨大能力缺口；任务还涵盖多站点协同与长时序目标。
- **Core thesis (EN)**: Prior web-agent benchmarks are too simple, with executable-code observations and short single-step tasks. WebArena offers a functional, reproducible web ecosystem (shopping, forum, GitLab, map, knowledge base) for end-to-end task completion.
- **Novelty (EN)**: 812 natural-language tasks with deterministic success judgments scored functionally rather than by text similarity, revealing a wide gap: the best GPT-4 agent reaches 14.41% against 78.24% for humans, with tasks spanning cross-site coordination and long horizons.

### VOYAGER: An Open-Ended Embodied Agent with Large Language Models（Wang et al., 2023）

- **PDF**：[10_智能体与工具使用/VOYAGER - An Open-Ended Embodied Agent with Large Language Models.pdf](</home/kun/Desktop/paper/completed/10_智能体与工具使用/VOYAGER - An Open-Ended Embodied Agent with Large Language Models.pdf>)
- **核心论点（中）**：开放世界智能体需要无需梯度更新的持续学习。VOYAGER 用 GPT-4 做课程生成、把已学会的行为以可执行代码形式存入技能库、并用环境反馈与执行错误做迭代提示修正。
- **创新点（中）**：三个组件（自动任务课程、随任务增长的技能代码库、带 critic 信号与报错回流的迭代提示机制）组成的首个 LLM 驱动终身学习具身智能体；在 Minecraft 中相比 AutoGPT/ReAct 等获得 3.3 倍独特物品、2.3 倍探索距离、15.3 倍更快的科技树里程碑达成，且技能库可迁移到新世界零样本泛化。
- **Core thesis (EN)**: Open-ended agents need continual learning without gradient updates. VOYAGER uses GPT-4 to propose tasks, stores mastered behaviors as executable code in a growing skill library, and refines programs through environmental feedback and execution errors.
- **Novelty (EN)**: The first LLM-driven lifelong-learning embodied agent, combining an automatic task curriculum, an ever-growing code skill library and iterative prompting with critic feedback and error signals; in Minecraft it obtains 3.3x unique items, 2.3x exploration distance and unlocks tech-tree milestones 15.3x faster than AutoGPT/ReAct-style baselines, with the skill library transferring zero-shot to new worlds.

---

## 11. 检索增强生成

**主题定位**：把外部知识接入生成，既缓解幻觉，也把"数据源可信度"变成安全议题（与第 4 组间接提示注入直接相关）。

### Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks（Lewis et al., NeurIPS 2020）

- **PDF**：[11_检索增强生成/Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.pdf](</home/kun/Desktop/paper/completed/11_检索增强生成/Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.pdf>)
- **核心论点（中）**：参数化记忆（模型权重）难以精确编辑且容量有限。把预训练 seq2seq 生成器与非参数化密集索引（Wikipedia 向量索引）通过神经检索器耦合，事实知识便可在测试时更换而无需重训。
- **创新点（中）**：提出 RAG 统一架构与两种解码变体：RAG-Sequence（整句共用一组检索文档）与 RAG-Token（逐 token 跨文档混合）；在开放域问答、TriviaQA、WebQuestions 等知识密集任务上超越纯参数化基线并改善摘要与事实核查的事实性，同时把"更新知识"变成改索引而非改权重。
- **Core thesis (EN)**: Parametric memory is hard to edit precisely and limited in capacity. Coupling a pretrained seq2seq generator with a non-parametric dense index over Wikipedia through a neural retriever lets factual knowledge be swapped at test time without retraining.
- **Novelty (EN)**: Introduces the unified RAG architecture with two marginalization variants, RAG-Sequence (one document set per answer) and RAG-Token (per-token mixing across documents), beating parametric-only baselines on open-domain QA, TriviaQA and WebQuestions and on factuality in summarization and fact-checking, while making knowledge updates an index edit rather than a weight edit.

### Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection（Asai et al., ICLR 2024）

- **PDF**：[11_检索增强生成/Self-RAG - Learning to Retrieve, Generate, and Critique through Self-Reflection.pdf](</home/kun/Desktop/paper/completed/11_检索增强生成/Self-RAG - Learning to Retrieve, Generate, and Critique through Self-Reflection.pdf>)
- **核心论点（中）**：每句都检索既浪费也可能引入噪声。Self-RAG 训练模型自己发出反思 token，按需决定是否检索、评价检索段落是否相关、检查生成是否被证据支持，并据这些信号自选答案。
- **创新点（中）**：用 GPT-4 标注批评数据，把"检索决策 + 生成后自评"全部编进同一语言模型的词表，取消外部批评器；7B/13B 在知识密集基准上超过 ChatGPT 与检索增强 Llama2-chat，并可在推理时动态调节事实性与流畅性的权衡；"正确却无段落依据"的比例仅 2%，而基线为 15-20%，这是证据支撑度量的关键改进。
- **Core thesis (EN)**: Retrieving on every sentence is wasteful and can inject noise. Self-RAG trains the model to emit reflection tokens that decide when to retrieve, judge passage relevance, verify whether its generation is evidence-supported and select its own answer from those signals.
- **Novelty (EN)**: Uses GPT-4-labeled critic data and folds retrieval decisions plus post-generation self-evaluation into the same model vocabulary, removing external critics; 7B/13B beat ChatGPT and retrieval-augmented Llama2-chat on knowledge-intensive benchmarks with a test-time factuality-fluency knob, and correct predictions unsupported by passages fall to 2% versus 15-20% for baselines.

### CRAG: Corrective Retrieval Augmented Generation（Yan et al., ICLR 2025）

- **PDF**：[11_检索增强生成/CRAG - Corrective Retrieval Augmented Generation.pdf](</home/kun/Desktop/paper/completed/11_检索增强生成/CRAG - Corrective Retrieval Augmented Generation.pdf>)
- **核心论点（中）**：RAG 的短板在检索器本身不可靠：无论相关与否，检索结果总会被塞进提示。CRAG 在检索器与生成器之间插入一个轻量检索评估器，把"检索质量"变成显式信号并据此触发不同动作。
- **创新点（中）**：三态置信（正确 / 含糊 / 错误）驱动分派：判为正确时做"分解-再组合"式知识精炼以剔除噪声，判为错误时回退到网络搜索，含糊时两者并用；与现有 RAG 架构即插即用，在 4 个数据集上提升鲁棒性，是对检索层失准与污染最直接的工程缓解。
- **Core thesis (EN)**: RAG is bottlenecked by an unreliable retriever that always feeds its results into the prompt regardless of relevance. CRAG inserts a lightweight retrieval evaluator between retriever and generator, turning retrieval quality into an explicit signal that triggers different actions.
- **Novelty (EN)**: Confidence-graded actions over correct/ambiguous/incorrect labels, with decompose-then-recompose knowledge refinement to strip noise on good hits and a web-search fallback on bad ones; plug-and-play with existing RAG stacks, improving robustness on four datasets and giving the most direct engineering mitigation against a miscalibrated or poisoned retrieval layer.

### RAGAS: Automated Evaluation of Retrieval Augmented Generation（Es et al., 2023）

- **PDF**：[11_检索增强生成/RAGAS - Automated Evaluation of Retrieval Augmented Generation.pdf](</home/kun/Desktop/paper/completed/11_检索增强生成/RAGAS - Automated Evaluation of Retrieval Augmented Generation.pdf>)
- **核心论点（中）**：RAG 必须同时评检索与生成两件事，而传统指标要么需要人工参考答案、要么只测文本相似度。RAGAS 给出不依赖标准答案（reference-free）的三个维度：检索相关性、生成对检索上下文的忠实度、生成答案本身的质量。
- **创新点（中）**：用 LLM 自身作为判断器，并把"模型是否真的用上了检索段落"这一失败模式量化成 faithfulness 指标，使无人工标注的生产环境 RAG 回归测试成为可能；成为主流 RAG 评测工具链的起点。
- **Core thesis (EN)**: RAG must be scored on retrieval and generation at once, yet classical metrics either need human references or only measure textual similarity. RAGAS provides reference-free dimensions: retrieval relevance, faithfulness of the answer to the retrieved context, and answer quality.
- **Novelty (EN)**: Uses the LLM itself as judge and turns the "did the model actually use the retrieved passages" failure mode into a measurable faithfulness score, making RAG regression testing feasible in production without human references; the starting point of mainstream RAG evaluation tooling.

---

## 12. 安全范式与综述

**主题定位**：从"打补丁式防御"跳到"体系级安全范式"。两篇中文内生安全文献提供构造级思路，一篇英文综述提供 LLM 安全版图与研究缺口清单。

### 网络空间内生安全发展范式（邬江兴，中国科学：信息科学 2022, 52(2): 189-204）

- **PDF**：[12_安全范式与综述/网络空间内生安全发展范式.pdf](</home/kun/Desktop/paper/completed/12_安全范式与综述/网络空间内生安全发展范式.pdf>)
- **核心论点（中）**：针对"未知的未知威胁"，依赖漏洞挖掘与补丁修复的外挂式安全在逻辑上不可能穷尽所有缺陷；必须转换范式，让安全成为系统构造自带的属性（内生安全），通过冗余与异构使错误与攻击无法改变系统功能。
- **创新点（中）**：提出 DHR（动态异构冗余）构造作为工程实现路径，以"相对正确公理"取代对绝对正确性的依赖，论证在开放、未知威胁环境下可由构造本身产生安全增益（从"攻防对抗"走向"确定性防护"）。对大模型安全的启示是：与其指望对齐完备，不如在执行层引入多模冗余与裁决机制。
- **Core thesis (EN)**: Against "unknown unknowns", security bolted on through vulnerability discovery and patching cannot logically exhaust all defects. Safety must instead become an intrinsic property of the system's construction, achieved through redundancy and heterogeneity so that errors and attacks cannot alter system function.
- **Novelty (EN)**: Proposes the DHR (Dynamic Heterogeneous Redundancy) construction as the engineering path and substitutes a "relative correctness axiom" for reliance on absolute correctness, arguing that safety gains can be generated by construction itself under open, unknown threats. The read-across for LLMs: add redundant execution paths plus adjudication at the execution layer instead of hoping alignment is complete.

### 人工智能内生安全机制研究（陆昕怡 等，科学研究与应用 2025, V1(9)）

- **PDF**：[12_安全范式与综述/人工智能内生安全机制研究.pdf](</home/kun/Desktop/paper/completed/12_安全范式与综述/人工智能内生安全机制研究.pdf>)
- **核心论点（中）**：AI 内生安全风险源于模型自身的可计算脆弱性，因此第一步是把脆弱性变成可度量对象（边界距离、局部曲率、特征敏感度），再据此构建可自调节的安全机制。
- **创新点（中）**：给出一套面向工程落地的脆弱性量化指标体系，并提出"感知-认知-调节"三层闭环与主动免疫机制，把内生安全从理念推进到可监测、可反馈、可干预的闭环流程；与大模型侧的探针与表示分析路线（safety basin、refusal direction、safety-aware probing）在方法论上同构。
- **Core thesis (EN)**: Intrinsic AI safety risk stems from computable vulnerabilities inside the model itself, so vulnerability must first become measurable (boundary distance, local curvature, feature sensitivity) before a self-regulating safety mechanism can be built on those measurements.
- **Novelty (EN)**: Supplies an engineering-oriented vulnerability quantification scheme plus a three-layer perceive-cognize-regulate closed loop with active-immunity mechanisms, moving intrinsic safety from principle to a monitorable, feedback-driven, intervenable process; methodologically parallel to LLM-side probing and representation analysis (safety basin, refusal direction, safety-aware probing).

### A Survey on LLM Security and Privacy: The Good, The Bad, and The Ugly（Yao et al., High-Confidence Computing 4 (2024) 100211）

- **PDF**：[12_安全范式与综述/A Survey on LLM Security and Privacy - The Good, The Bad, and The Ugly.pdf](</home/kun/Desktop/paper/completed/12_安全范式与综述/A Survey on LLM Security and Privacy - The Good, The Bad, and The Ugly.pdf>)
- **核心论点（中）**：LLM 的安全效应是三面的：它既是防御工具（The Good），也可被攻击者滥用（The Bad），同时自身带着漏洞（The Ugly）。任何只谈单面的评估都会误导部署决策。
- **创新点（中）**：以三段式分类组织整个领域文献（有益应用 / 攻击性使用 / 漏洞与防御），逐类盘点攻防手段与隐私风险；结论指出 LLM 在代码安全与数据保密类任务上收益明确，但用户级攻击风险突出，而模型与参数提取、安全指令微调等方向仍属薄弱环节，直接给出研究缺口清单（本知识库第 1、2、7 组正落在这些缺口上）。
- **Core thesis (EN)**: LLM security effects are three-sided: they serve as defensive tools (Good), get abused by attackers (Bad), and carry their own vulnerabilities (Ugly). Any one-sided assessment misleads deployment decisions.
- **Novelty (EN)**: Organizes the field into beneficial applications, offensive use, and vulnerabilities with defenses, inventorying attacks, defenses and privacy risks per class, and concludes that gains are clearest for code security and data confidentiality while user-level attack risk is significant and model/parameter extraction plus safe instruction tuning remain weak, producing an explicit gap list that sections 1, 2 and 7 of this knowledge base sit inside.

---

## 如何扩展本知识库

1. **下载**：把新 PDF 直接放进 `need_organization/`（子目录随意，也可散放）。
2. **整理**：让助手（或自己）执行：确认真实标题 → 重命名为标题 → 判断归属主题（可新建 `completed/13_xxx/`）→ 用 `_templates/PAPER_TEMPLATE.md` 写一条中英双语条目 → 从 `need_organization/` 移动到 `completed/<主题>/`。
3. **查重**：先比对已有 67 篇标题；完全重复放 `_archive/duplicates/`，同一论文的旧版本或审稿版放 `_archive/versions/`，不要删除。
4. **登记**：在文件顶部"论文总数"处 +1，更新"最后更新"日期；若新增主题目录，同步补进"目录 / Index"。
5. **主题图谱建议**：新条目尽量补一句"与本组其他论文的关系"，让每组形成链条而非清单。当前主线：
   - 安全主线：`1 机理` → `2 防御` → `3 越狱攻防` → `4 智能体注入` → `12 范式`
   - 能力主线：`6 对齐与数据` → `7 参数高效微调` → `8 推理` → `9 规划` → `10 智能体` → `11 RAG`
   - 测量底座：`5 评测基准与工具` 为两条主线提供可复现的评价口径

## 待整理 / Pending

`need_organization/` 当前为空（仅有 `.gitkeep` 占位）。收件箱里的文件即待整理项，用 `ls need_organization` 查看；整理完成后文件会移入 `completed/<主题>/` 并在上文对应分组新增条目，因此本节始终保持"为空"即为健康状态。
