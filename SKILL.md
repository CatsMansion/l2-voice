---
name: l2-voice
description: "把英文文本改写成特定母语的国际学生笔迹，用于降低 AI 检测率。当用户要求「降英文 AI 率」「英文去 AI 味」「改得像留学生写的」「humanize 英文」「英文论文润色到不像 AI」「让这段英文不像是 AI 写的」时使用。工作机制：抬高词汇意外度与句长波动（perplexity/burstiness）、植入系统化且稀疏的母语迁移标记、清英文 AI 词表与公式化句式、还原该 L1 的论文宏观结构。含人格校准脚本，可从使用者旧作文提取真实笔迹。不承诺通过 Pangram 类 ESL 专训分类器。"
agent_created: true
---

# L2 Voice

把英文改写成「某个母语、努力、有具体生活」的人写的。目标不是骗过检测器，是**让文本读起来有一个具体作者**——AI 率下降只是副产物。

---

## ⛔ 开工前必须接受的三条，否则不要用这个 skill

**1. 不许把英语写简单。**
低词汇多样性 = 低意外度 = 判为机器。Liang et al. (*Patterns* 2023) 实测：非母语人类作文被 7 个检测器平均误判 **61.22%**；把母语作文改写成「非母语口吻」，误判从 5.19% 涨到 **56.65%**。
⇒ 杠杆是**抬高意外度**，不是降低水平。要「不均匀」，不要「差」。

**2. 不许撒随机错误。**
真人的弱点是有规律的：反复在同一个地方错。均匀撒错 = 伪随机噪声 = 另一种机器特征。全文只许 **2–3 类**标记，每类反复出现。

**3. 不许编具体细节。**
具体数字、设备型号、过程细节是**最有效**的人味来源，也是最严重的造假风险。这些必须由使用者提供真实素材。问，不许编。

---

## 流程

### Phase 0 · 问诊

**按顺序走，能跳就跳：**

**① 有旧作文样本？** → 直接跳 Phase 1，本阶段只补「文体」。
**② 用户愿意填量表？** → 走 A 路线（15 题，能定档）
**③ 都不愿意？** → 走 B 路线（问 4 题，够用但粗）

#### A 路线 · 学习路径量表（推荐）

```bash
python scripts/intake.py --ask                                   # 交互式逐题问
python scripts/intake.py --template > answers.json               # 或拿骨架填
python scripts/intake.py --answers answers.json --write profiles/  # 出 persona 草稿
```

量表把学习史映射到四个参数：`marker_set`（zh / g15）、`script_band`、`main_failure`、`marker_candidates`。构念与依据见 `references/intake.md`。

⛔ 量表的输出是**先验**。它可能命中冲突（脚本会打印），冲突必须追问，不许平均掉。
⛔ 置信度上限 0.9。不许对用户说「量表测出你的水平是 X」。

#### B 路线 · 四问快诊（不问量表时）

| 项 | 取值 | 缺省 |
|---|---|---|
| 文体 | `academic`（论文/报告）/ `post`（帖子/邮件/文书） | academic |
| 目标 L1 | zh / ko / ja / vi / ar / es | zh |
| **几岁到英语国家长期读书** | 没去过 / <12 / 12–15 / 16–18 / 18 后 | — |
| 旧作文样本 | 3–5 篇同文体、≥300 词、未经 AI 润色 | 无则降级，须告知 |

**⚠️ 水平档不按 IELTS 选，按到达年龄选。** 这是最容易搞错的一步：

| 情况 | 档 | 指纹库 | 核心动作 |
|---|---|---|---|
| 国内读完本科再出国读研 | 6.0–7.5 | `references/l1/zh.md` | **植入**母语迁移错误 |
| **12–18 岁到达，且在英语国家读完中学** | **g15** | `references/gen15.md` | **去模板化** + 极少量语域泄漏 |

研究依据：de Kleine et al. 2024 发现分界线是**到达年龄 12 岁**——12 岁前到达者写作接近单语母语者，12 岁后保留残余痕迹。这一档口语常近母语但写作仍留痕，用 `l1/zh.md` 的配方会写出一个「英语很差的人」，与本人不符。

⛔ 报 IELTS 7.5 不等于该用 7.5 档。先问「几岁来的」。

#### 无论哪条路线，academic 文体必须问第五项

> 「这篇里有哪些只有你知道的东西？具体的数字、设备或软件版本、卡住过的地方、导师说过的话。给我 3 条，没有就写『没有』。」

没有真实素材时，P0 层（见 Phase 3）跳过，并在交付时说明「人味只做到句法层」。

### Phase 1 · 建 Persona

有样本：

```bash
python scripts/l2metrics.py --samples "<样本目录>" --json
```

拿到数值后按 `references/calibration.md` §3 人工补脚本查不出的项，填 `templates/persona-card.md`，存到 `profiles/<id>.md`。

无样本：走 `references/l1/zh.md` §H 的默认配方，**必须打印降级告警**：

> 「没给旧作文，我按中文母语者 B 档通用模板做。能解决『不像 AI』，解决不了『不像你』。有 3 篇旧作文给我，我重跑校准。」

⛔ 已有 `profiles/` 存档时直接读，不要重新推。

### Phase 2 · 体检原文本

```bash
python scripts/l2metrics.py --text draft.txt --genre academic --band 7.0
```

记下四个数：`sent_cv`、`connector_per_1k`、`ai_word_per_1k`、`AI 短语命中`。这是改写前基线。

同时人工标出**结构层高风险段**：文献综述、方法描述、节末小结——这些模板感最强，检测器和导师都最先看这里。

### Phase 3 · 改写（严格按优先级，预算用完就停）

#### P0 · 具体化（收益最高，风险最低）

把泛化句换成使用者提供的真实细节。

- 前：`The experiment took longer than expected.`
- 后：`The experiment took eleven days, two of which went to a missing comma in a config file.`

⛔ 没有真实素材就跳过，不许编。

#### P1 · 结构层（论文的主战场，见 `references/academic-zh.md`）

按收益/风险排序，默认做 1–5：

1. 引用动词统一换成 `show / found / pointed out / suggested`（删掉 `demonstrate/elucidate/underscore/highlight`）
2. 段落参差化：挑 2 段把 topic sentence 挪到段中，删 2 个段末小结句，让一段只有 2 句
3. hedging 拆散：结论段成串的 hedge 只留 1 个；删所有 `it should be noted that` 类整句 hedge；在某个具体数据句加一个单点 hedge
4. 结论段保留「不足与展望」，措辞朴素化
5. 加一段 2–3 句的让步，**让步完不立刻推翻**（承认反方部分成立）

⛔ 6（thesis 后移）、7（综述罗列化）、8（第一人称不一致）必须先问——7 会降论文质量。

#### P2 · 句法层

- 拆长句、并短句，制造双峰：让至少 15% 的句子 ≤10 词，12% ≥28 词
- 打破连续 3 句长度接近的段落
- 删所有 em dash（`—`）→ 逗号 / 句号 / `and`
- 分号降到 ≤2/千词
- 每段起手式换一遍：不许连续两段用同一种开头结构

#### P3 · 词汇层

按 `references/ai-tells-en.md` 清词：

- 一档词（`delve / tapestry / realm / leverage / foster / seamless ...`）见到就换
- `very + 弱形容词` → 精确词（`very big` → `substantial`）
- 三段式排比改成两项或四项

#### P4 · 指纹层（⛔ 最后做，只按 persona 的固定弱点来）

从 `references/l1/zh.md` 或 `references/gen15.md` 和 persona card 里取**已经定好的 1–3 类**，按密度植入。不要临时换类型。

**B 档（6.5–7.0，中文迁移）默认配方（1000 词）：**

```
A1 长名词短语末尾漏 the        ×3–5
C9 the reason is because       ×1
D1 Although ... but ...        ×1（只一次）
E1 或 E5 套语残留              ×1–2
F  a lot of 类语域滑落         ×1
```

合计 7–11 处 / 千词，**类型数 = 4**。类型数超 4 就砍掉一类，密度超 12 就删几处。

**g15 档（中学出国）默认配方（1000 词）：**

```
G15-REG-02 a lot of / a bit    ×1–2
G15-LEX-02 make an improvement ×1
G15-DIS-01 句首 But            ×1
（手动）-ed/-s 脱落             ×1
```

合计 **1–4 处 / 千词，类型数 1–2**。⛔ 比中文迁移档更稀疏；这一档的重活在 P1 去模板化，不在 P4。

#### P5 · 标点与排版

em dash 归零、加粗行内标题归零、Title Case 改 sentence case、删装饰性列表。

### Phase 4 · 闸门

```bash
python scripts/l2metrics.py --text rewritten.txt --genre academic --band 7.0
```

必须全绿或全在区间内。逐项看，**不要只看有几项 HIGH/LOW**：

**硬闸门**（有机制支撑，必须过）：

| 指标 | 要求 | 不达标怎么办 |
|---|---|---|
| `ai_word_per_1k` | ≤3 | 清一档词 |
| `ai_phrases` | =0 | 全删 |
| `connector_per_1k` | ≤12 | 删 `furthermore/moreover/additionally` |
| `em_dash` | =0 | 全换 |
| `sent_cv` | 0.36–0.72 | 低 → 拆/并句 |
| `uniform_run` | ≤2 | 有 3 句同长 → 改一句 |
| `l1_marker_per_1k` | 按 band（7.0 → 3–8） | 低 → 补；高 → 删 |
| `l1_marker_types` | 2–3（硬上限 4） | 超 → 砍最弱的一类 |
| `sent_init_top_share` | ≤16% | 句首最频词占比超标 → 换开头，见 Phase 4.5 |
| `sent_init_article_share` | ≤24% | 冠词/指示词起句超标 → 换开头 |
| `flat_excess` | ≤1.8 | 节奏比随机还平 → 拆/并句 |

**过度编辑轴**（单独打印，判 AI 的主战场）：

| 指标 | 参考 | 怎么读 |
|---|---|---|
| `sent_init_top_share` | 越低越好 | 全篇 1/4 句以 `The` 开头 = 最强机械信号 |
| `sent_init_article_share` | ≤24% | `The/This/These/A/An/Such` 起句占比 |
| `sent_init_type_ratio` | 0.45–1.0 | 句首词种类 ÷ 句数，越高越不重复 |
| `parallel_cv` | 0.45–1.60 | 段长变异。**低于 0.45 才是问题**，别反向硬拉 |
| `stance_per_1k` | 不设闸门 | 有作者判断就涨。仿论文时 0 是可疑的 |
| `hedge_per_1k` | 不设闸门 | 学术 4–8 正常 |
| `meta_per_1k` | 不设闸门 | 「本文做什么」类元话语 |

⛔ **`em_dash` 只数「当标点用」的破折号**：U+2014 全算，U+2013 只在前后带空格时算。
`2021–2024`、`manager–firm`、`exposure–log-weight` 这类连接号不算——否则正常论文会被判满屏 HIGH。

⛔ **`flat_triplets` 不能看绝对值**：文本越长攒得越多，9k 词必然比 200 词高十倍。
脚本现在给的是 `flat_excess` = 实测比例 ÷ 同长度同方差随机序列的比例，>1.8 才算真平板。

**参考值**（弱代理，不判红，只用来读趋势）：

| 指标 | 参考区间 | 说明 |
|---|---|---|
| `sent_mean` | 16–26 | 学术散文合法范围很宽，别硬调 |
| `short_ratio` | 7–22% | 有人天生短句多，不算错 |
| `long_ratio` | 12–34% | 同上 |
| `fp_per_1k` | 2–20 | 学科差异大 |
| `parallel_cv` | 0.45–1.60 | 段长变异，段数 <3 时跳过 |

### Phase 4.5 · 破句首单调

`sent_init_top_share` / `sent_init_article_share` 超标时，**不要逐句改词，要换开头方式**。
同一段里连续 3 句都用同一类开头（尤其 `The + 名词`），换法按这个顺序试：

| 换法 | 例 |
|---|---|
| 状语前置 | `In the benchmark specification, ...` / `Across all four outcomes, ...` |
| 分词/不定式 | `Excluding 2022, the coefficient ...` / `To see why, consider ...` |
| 主题前置（作者习惯） | `Churn measures ...` / `Active Share describes ...` |
| 判断句开头 | `What the design cannot do is identify a cause.` |
| 短句断句 | `The picture is firmer among existing holders.` |
| 序数并列 | `First, ... Second, ... Third, ...`（一段最多用一次） |

⚠️ 序数并列一次用满三段会让句首「种类」冲到 1.0，反而整齐得可疑。**换完要回看 top4 里有没有新模范。**

⚠️ 破单调会让字数涨 **6–10%**。有字数上限时，同步压掉冗余从句，别让全篇膨胀。

⚠️ **冠词漏用、语域滑落、套语残留这三类正则查不出来，必须人工数**，然后用 `--manual-markers N` 计入闸门。不数就等于没加。

```bash
python scripts/l2metrics.py --text rewritten.txt --band 7.0 --manual-markers 5
```

⚠️ **判据只保证「做没做对」，不保证「好不好看」。** 指标全绿但读起来还是塑料味，说明 P0 层没做——回去补真实细节。

### Phase 5 · 交付

输出三块，不要输出「AI 率预测值」：

1. **改写后全文**
2. **改动表**：每处标记改动 → 对应 `l1/zh.md` 的条目 ID + 为什么这个 L1 会这样写
3. **前后指标对照表** + **未做的事**（哪些 P 层跳过了、为什么）

⛔ **不许给 AI 率预测数字。** 本机没有检测器，猜一个就是骗人。使用者要测，让他自己去跑，把结果贴回来记进 `profiles/`。

---

## 边界（对使用者必须说清）

| 目标 | 结论 |
|---|---|
| 统计类检测器（GLTR / Fast-DetectGPT / ZeroGPT 免费版） | 大概率能压低 |
| GPTZero | 部分能（RAID 上 66.5%） |
| Originality | 难（RAID 上 85.0%） |
| Pangram | ⛔ 不承诺。ESL 语料专训，ACL 2025 实测对 humanized 文本 TPR 96.7% |
| 打字节奏 / 版本历史 / viva | ⛔ 文本层完全无效 |

**长论文特别注意**：4000 词以上的文档上 Turnitin 基本隐形（2026 年 160 篇硕士论文实验：40 篇纯 AI 检出 0%，全落在界面隐藏的 0–20% 带）。所以长论文的真实裁判是导师和答辩，验收标准应是「读起来像这个人写的」，不是「分数过线」。

一句话必须写进交付：

> 「这个 skill 改的是文风，不是写作过程。如果被质疑，唯一硬证据是草稿版本历史、检索笔记和能现场解释的论证链——那三样它给不了你。」

---

## 文件索引

| 文件 | 什么时候读 |
|---|---|
| `references/mechanism.md` | 改这个 skill 之前必读。防止把「抬意外度」改回「降水平」 |
| `references/l1/zh.md` | 6.0–7.5 档。中文母语者的语法级清单 + 配方 |
| `references/gen15.md` | **g15 档（中学出国）**。逻辑相反：去模板化 + 极少量语域泄漏 |
| `references/academic-zh.md` | 论文文体必读。结构层指纹，收益比语法层高 |
| `references/ai-tells-en.md` | Phase 3 P3 清词时 |
| `references/calibration.md` | Phase 1 有样本时 |
| `references/intake.md` | Phase 0 A 路线。量表的构念、相关系数、边界 |
| `templates/persona-card.md` | Phase 1 输出格式 |
| `scripts/intake.py` | Phase 0 量表打分 |
| `scripts/l2metrics.py` | Phase 2 / 4 体检 |
| `profiles/` | 人格存档，复用不要重推 |
