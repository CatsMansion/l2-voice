# 机制说明 —— 为什么这个 skill 长这样

> 这份文件的作用是**防止未来把 skill 改错方向**。任何对 SKILL.md 的修改，先读这里。
> 数据出处见文末。

---

## 1. 检测器到底在看什么

主流检测器不是一个东西，是三套不同机制叠在一起：

| 机制 | 代表 | 读什么 | 怎么骗 |
|---|---|---|---|
| **统计 / 意外度** | GLTR、DetectGPT、Fast-DetectGPT、Binoculars | token 级 log-likelihood（perplexity）+ 句长波动（burstiness） | 抬词汇意外度、造句长双峰 |
| **微调分类器** | GPTZero、Turnitin、Originality、Pangram | 表面特征 + 训练集里的分布指纹 | 只能靠"不像训练分布"，没有稳定解法 |
| **水印 / 溯源** | SynthID、绿名单水印 | 生成时的采样痕迹 | 文本层改不掉，只能用非官方通道 |

⛔ **三套机制的打法互相冲突。** 抬 perplexity 对付第一类有效，但微调分类器可能反而把"故作高深"当成 AI 特征。所以任何"保证过检测器"的承诺都是假的。

---

## 2. ⛔ 最重要的一条：不要把英语写简单

这是本 skill 存在的前提，也是最初设计假设里错的那一半。

Liang et al. (*Patterns*, 2023) 用 91 篇人类写的 TOEFL 作文喂 7 个主流检测器：

| 样本 | 平均假阳性 |
|---|---|
| 非母语人类作文 | **61.22%** |
| 母语（美国八年级）人类作文 | 5.19% |
| 母语作文**被改写成"非母语口吻"** | 5.19% → **56.65%** |
| 非母语作文**词汇被提升到母语水平** | 61.3% → **11.6%** |

机制已经定位到 perplexity：被全部 7 个检测器一致误判的那批作文，perplexity 显著更低（P = 9.74e-05）。

结论：**低词汇多样性 + 低句法复杂度 = 低意外度 = 被判机器。**
⇒ 把文字改成"英语不熟"，AI 率**上升**。
⇒ 这个 skill 的杠杆是**提高意外度**，不是降低水平。

---

## 3. 那"像留学生"这件事还能不能用？

能，但要换个理解方式。

「特别努力的留学生」不是「英语差的留学生」。前者是**不均匀**的人：

- 词汇野心很高（用 *conflate*、*attenuate*、*at the expense of*），但冠词会漏
- 论证顺序是中文训练出来的（先铺背景，再点题；综述罗列，不批判整合）
- 句长忽长忽短，中间夹一句 6 个词的
- 同一个语法弱点反复犯，不是均匀撒错

「不均匀」= 高 burstiness + 局部高 perplexity。这才是要仿的东西。

⭐ **一个关键的巧合**：`article deletion`（删冠词）既被 RAID 收录为标准对抗攻击之一，又是中日韩越母语者最典型的语法漏洞。一个改动同时满足「像人」和「打检测器」。这是全案唯一一处两个目标同向的地方。

⛔ **反向冲突**：词汇丰富度。母语迁移要求"词汇窄"，检测器要求"词汇不确定"。必须选后者，用**结构不均匀**替代**词汇贫乏**来承载 L2 感。

---

## 4. 为什么错法必须「系统化且稀疏」

真人的语言弱点是有规律的：一个中文母语者会**反复**在冠词上出错，但不会今天漏冠词、明天漏时态、后天拼错实词。

如果在全文随机撒错：
- 语法错误密度均匀 ⇒ 统计上像伪随机噪声 ⇒ 本身就是一种机器特征
- 且读起来像"故意弄脏"，不像"这个人就这么写"

所以闸门里 `l1_marker_types` 卡在 **2–3 类**，就是这个原因。宁可只用一个弱点犯 6 次，不要 6 个弱点各犯 1 次。

---

## 5. 为什么不能用实词拼写错误

| 错误类型 | 读者读成什么 |
|---|---|
| 冠词 / 介词 / 复数漏用 | 「这人母语不是英语，但英语不错」 ✅ |
| 实词拼错（*recieve*、*enviroment*） | 「这人英语很差 / 有阅读障碍 / 打字不检查」 ❌ |
| 随机时态漂移 | 「这人写作能力有问题」 ❌ |
| 双连词（Although...but） | 「中文母语者」⭐⭐ 最准的指纹 |

规律：**功能词层的错 = L2 指纹；实词层的错 = 能力问题。** 只动功能词。

---

## 6. 论文场景的特殊约束

学术体裁天生低意外度。方法段、文献综述怎么写都规整。所以：

1. **人味不能靠降级到口语**，只能靠论文内部的指纹：真实数据、具体细节、论证顺序、引用方式。
2. **语法错误密度必须比口语文本低一半以上**。4000 词论文里 30 个冠词错误 = 导师判"语言不合格"，不是好结果。
3. **长文档上检测器基本失效**。2026 年一组 160 篇 ≥4000 词硕士论文的实验：
   - Turnitin 对 40 篇纯 AI 论文检出 **0%**（全落在 0–20% 的界面隐藏带）
   - 对混合文本 60%，对已人性化 50%
   - Pangram 对纯 AI 65%，对混合/人性化 92.5%
   
   ⇒ 交长论文时，真正抓人的不是检测器，是**导师 + viva + 版本历史**。
   ⇒ 所以验收标准定为「读起来像这个人写的」，**不是**「过某个检测器」。

---

## 7. 强度边界（必须对用户说清，不许含糊）

| 目标 | 能不能过 |
|---|---|
| 统计类检测器（GLTR / Fast-DetectGPT / ZeroGPT 免费版） | 大概率能压下去。RAID 上这类工具在 5% FPR 下准确率只有 62–74% |
| GPTZero | 部分能。RAID 上 66.5%；对同形字几乎免疫（掉 0.3 点） |
| Originality | 难。RAID 上 85%，且有抗攻击训练 |
| Pangram | ⛔ **不要承诺**。它用 16.5 万条 ESL 样本训练，Russell et al. (ACL 2025) 实测对 humanized 文本 TPR 96.7% |
| 打字过程 / 版本历史 / viva | ⛔ 文本层完全无效 |

---

## 8. 出处

- Liang, Yuksekgonul, Mao, Wu, Zou. *GPT detectors are biased against non-native English writers.* Patterns 4(7), 2023. https://www.sciencedirect.com/science/article/pii/S2666389923001307
- Dugan et al. *RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors.* ACL 2024.（12 检测器 / 620 万条生成 / 统一 5% FPR）
- Russell, Karpinska, Iyyer. ACL 2025.（300 篇 humanized 文章 × 5 名专家标注）
- Krishna et al. *DIPPER / Paraphrasing evades detectors.* NeurIPS 2023.
- Weber-Wulff et al. *International Journal for Educational Integrity*, 2023.
- Perkins et al. *International Journal of Educational Technology in Higher Education* 21:53, 2024.
- Van Vlasselaer et al. *International Journal for Educational Integrity* 22:16, 2026.（160 篇 ≥4000 词论文）
- Shill & Nandi. *Attacking Only Half the Data: Two-Sided Evaluation of AI-Text Detector Robustness.* arXiv:2610.18151.
- Wikipedia, *Signs of AI writing*（WikiProject AI Cleanup 长期追踪）
