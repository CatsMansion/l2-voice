# 英文 AI 痕迹清单（去味用）

> 判据：**单个词出现不算证据，看密度和簇。** 一段里 3 个以上同簇词 / 一篇 >3 个/千词，就是问题。
> 来源：Wikipedia *Signs of AI writing*（WikiProject AI Cleanup 长期追踪）+ 多个独立编辑者的收敛词表。

---

## 1. 词汇三档

### 一档 · 见到就换（最强指示，几乎只出现在 2023 后的文本里）

`delve` `tapestry` `realm` `testament` `underscore` `pivotal` `multifaceted` `meticulous` `commendable` `seamless` `holistic` `leverage` `harness` `foster` `navigate` `showcase` `beacon` `cornerstone` `paramount` `noteworthy` `myriad` `plethora` `kaleidoscope` `interplay` `nuanced` `palpable` `bespoke` `transformative` `groundbreaking` `unprecedented`

**换法（几乎全是换成动词原形）**：

| AI 词 | 换 |
|---|---|
| delve into | look at / examine |
| leverage | use |
| utilize | use |
| facilitate | help |
| commence | start |
| foster | encourage / support |
| harness | use |
| showcase | show |
| underscore | show / suggest |
| navigate | deal with / work through |
| elevate | raise / improve |
| unlock / unleash | enable / release |
| holistic | whole / overall |
| robust | strong / reliable（或直接删） |
| seamless | smooth（或直接删） |

### 二档 · 降频（学术里合法，但密度高就是机器）

`crucial` `significant` `comprehensive` `essential` `fundamental` `profound` `remarkable` `notably` `particularly` `increasingly` `diverse` `complex` `key` `vital` `integral` `nuance` `landscape` `framework` `paradigm`

⚠️ 论文里 `significant` 有统计学含义，不能乱删。**只降频，不替换。**

### 三档 · 抽象名词（能具体化就具体化）

`journey` `landscape` `ecosystem` `endeavor` `symphony` `facet` `prowess` `treasure trove` `tapestry` `beacon` `testament`

---

## 2. 短语（一档，见到就删）

| 模式 | 处理 |
|---|---|
| `In today's fast-paced / ever-evolving / digital ...` | 整句删。100% 情况下开头会变强 |
| `It is important to note that` / `It's worth noting that` / `It should be noted` | 整句删，直接说那件事 |
| `It's not just X — it's Y` / `not only X but also Y` | 改成直接陈述。这是最强的句级指纹 |
| `plays a crucial/pivotal/vital role in` | 换成具体动作 |
| `stands as a testament to` | 删，或换 `shows` |
| `paving the way for` | 删 |
| `navigating the complexities of` | 删 |
| `a rich tapestry of` | 删 |
| `at the end of the day` | 删 |
| `shed light on` | `clarify` / `explain` |
| `serves as a reminder` | 删 |
| `in the realm of` | `in` |
| `a double-edged sword` | 删（陈词） |
| `more than just a` | 删 |
| `dive into`（非字面） | `look at` |

---

## 3. 标点与排版

| 项 | 规则 |
|---|---|
| **em dash（—）** | ⛔ 全文清零。AI 最响的一个 tell。换逗号、句号或 `and` |
| 分号 | 每千词 ≤2。AI 爱用分号堆并列 |
| 句中冒号 | 每千词 ≤2 |
| 加粗行内小标题 | ⛔ 清零。真人写散文不会中途加粗 |
| Title Case 标题 | 改成 sentence case |
| 装饰性 emoji / 项目符号列表 | 论文里清零 |
| 三段式排比 | 改成两项或四项。AI 的「rule of three」是硬指纹 |

---

## 4. 结构 tell

- **段落长度高度均匀**（每段 4–5 句）→ 打散
- **每段都有小结句** → 删掉一半
- **开头必铺场景**（`On a drab November morning...`）→ 删
- **结尾必总结 + 升华** → 改成直接收束或具体场景
- **每节都「先定义再展开」** → 打乱
- **通篇无第一人称、无具体数字、无专有名词** → 这是最致命的组合，见下

---

## 5. ⭐ 最有效的一条，不是删词

**AI 文本缺三样东西：具体数字、专有名词、只有作者知道的过程细节。**

| 缺 | 补 |
|---|---|
| 数字 | 具体到「11 天」「3 个模型」「87 份问卷」 |
| 专有名词 | 课程代码、仪器型号、软件版本、地名、人名 |
| 过程细节 | 「第 4 天卡在一个逗号上」「导师在 viva 上问的那句话」 |

⛔ **不许编。** 这三样必须由用户提供真实素材，模型虚构数字 = 学术造假，比 AI 味严重得多。
问法：「这篇里有哪些只有你知道的细节？数字、设备、时间、卡住的地方。」

---

## 6. 快速扫描命令

```bash
python scripts/l2metrics.py --text draft.txt --genre academic --band 7.0
```

看 `AI 词 x/千词`、`AI 短语命中`、`连接词`、`em_dash` 四行。归零或压到目标内再往下走。
