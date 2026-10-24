#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""l2metrics —— 英文文本的"像不像这个人的笔迹"度量器。

两种模式：
  1) 单篇体检：  python l2metrics.py --text draft.txt
  2) 人格提取：  python l2metrics.py --samples ./my_essays/  （聚合 3-8 篇旧作文）

输出人类可读表 + --json 时输出机器可读 dict。

⚠️ 这里所有阈值都是**工程默认值**，不是文献值。有旧作文样本时一律以
   --samples 跑出来的实测值为准，脚本会自己把阈值改写成 "calibrated"。
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import random
import re
import statistics as st
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ----------------------------------------------------------------------------
# 词表
# ----------------------------------------------------------------------------

# AI 高频词（英文）。来源：Wikipedia "Signs of AI writing" 追踪项目 +
# 多个独立编辑者整理表的交集。单个出现不构成证据，看**密度**。
AI_WORDS = """
delve delves delving tapestry realm landscape testament underscore underscores underscoring
pivotal multifaceted intricate intricacies meticulous meticulously commendable robust seamless
seamlessly holistic leverage leverages leveraging harness harnesses unlocking unleash unleash
elevate elevates fostering navigate navigating showcase showcases beacon cornerstone paramount
noteworthy crucial compelling transformative revolutionary cutting-edge game-changer utilize
utilizes facilitate facilitates commence synergy embark endeavor endeavours nuance nuances
interplay kaleidoscope myriad plethora nuanced palpable profound profoundly remarkably notably
crucially invaluable groundbreaking unprecedented bespoke versatile vibrant vivid whimsical
authentic comprehensive curated tailored empower empowers resonate resonates transcend transcends
illuminate illuminates unravel unravels catalyze catalyzes incentivize operationalize
unwavering unparalleled meticulously crafted emanating showcasing fostering
""".split()

# AI 高频短语
AI_PHRASES = [
    r"in today'?s (fast-paced|ever-evolving|modern|digital)",
    r"in an era of",
    r"it'?s not (just|only) [^.]{2,60}(,|—|-) ?it'?s",
    r"not only [^.]{2,80} but also",
    r"it is important to note",
    r"it'?s important to note",
    r"it is worth noting",
    r"it'?s worth noting",
    r"it should be noted",
    r"plays? a (crucial|pivotal|vital|key|significant) role",
    r"stand(s)? as a testament",
    r"paving the way",
    r"navigat(e|ing) the complexit",
    r"at the end of the day",
    r"a rich tapestry",
    r"(dive|delve) into",
    r"shed light on",
    r"serves? as a reminder",
    r"the (ever-)?(evolving|changing) landscape",
    r"in the realm of",
    r"a double-edged sword",
    r"the key (takeaway|to success) is",
    r"more than just a",
]

# AI 偏爱的过渡词（密度过高 = 机器感）
AI_CONNECTORS = [
    "furthermore", "moreover", "additionally", "however", "therefore", "thus",
    "consequently", "nevertheless", "nonetheless", "notably", "significantly",
    "in conclusion", "in summary", "overall", "ultimately", "conversely",
    "similarly", "likewise", "subsequently", "accordingly",
]

# 中文母语者（C1 级、海外 2 年以上）真实会漏的地方。⛔ 这些不是"英语差"，
# 是母语迁移的固定指纹。每条都要能在 references/l1/zh.md 里查到。
ZH_MARKERS: list[tuple[str, str, str]] = [
    # (id, 正则, 说明)
    ("ZH-CONJ-01", r"\bAlthough\b[^.!?]{2,90}?\bbut\b", "although...but 双连词（虽然…但是…）"),
    ("ZH-CONJ-02", r"\bBecause\b[^.!?]{2,90}?\bso\b", "because...so 双连词（因为…所以…）"),
    ("ZH-LEX-01", r"with the (rapid )?development of", "with the development of 套语"),
    ("ZH-LEX-02", r"\bmore and more\b", "more and more 直译（越来越）"),
    ("ZH-LEX-03", r"\bAs we all know\b|\bIt is well[- ]known that\b", "诉诸共识起手式"),
    ("ZH-DIS-01", r"\bLast but not least\b", "last but not least（高频且常误用）"),
    ("ZH-DIS-02", r"\b(Firstly|Secondly|Thirdly|First of all)\b", "序数式话语标记"),
    ("ZH-DIS-03", r"\bIn conclusion\b|\bTo sum up\b|\bAll in all\b", "段末收束套语"),
    ("ZH-COL-01", r"\blearn(ing|ed)? (a lot of |much |some )?knowledge\b", "learn knowledge（学知识）"),
    ("ZH-COL-02", r"\b(make|do|made|did|conduct)\s+(a|an)\s+(research|investigation|discussion|improvement)\b", "make a research 类搭配"),
    ("ZH-COL-03", r"\b(open|turn on) the light\b|\beat (the )?medicine\b|\bplay (the )?computer\b", "中式动宾搭配"),
    ("ZH-PREP-01", r"\bdiscuss about\b|\bemphasize on\b|\baccording to my opinion\b|\bin the contrary\b|\bon the contrary\b", "介词误用"),
    ("ZH-PREP-02", r"\bin terms of\b", "in terms of 当万能框（每篇超过 2 次才算过度）"),
    ("ZH-NOUN-01", r"\b(informations|equipments|advices|researches|softwares|feedbacks)\b", "不可数名词加复数"),
    ("ZH-DEG-01", r"\bvery (important|big|good|useful|helpful|serious)\b", "very + 弱形容词（该用精确词）"),
    ("ZH-TOP-01", r"\bAs for me\b|\bFor me,? I think\b|\bIn my opinion,? I think\b", "话题-评论结构冗余"),
]

# ----------------------------------------------------------------------------
# Gen 1.5 / ear learner 标记（到达年龄 ≥12 岁、在英语国家读完中学的人）
# 来源：Reid 的 ear learner 框架 + de Kleine et al. 2024 / Doolan 2017。
# 特征不是"中文迁移"，是"口语体漏进书面语" + "屈折词素"。见 references/gen15.md
# ----------------------------------------------------------------------------
GEN15_MARKERS: list[tuple[str, str, str]] = [
    ("G15-DIS-01", r"(?:^|[.!?]\s)(So|But|And|Also|Plus|Anyway|Still)[, ]",
     "句首口语连接词（So/But/And 起句）"),
    ("G15-REG-01", r"\b(don['’]t|doesn['’]t|didn['’]t|isn['’]t|aren['’]t|can['’]t|won['’]t|"
                   r"it['’]s|that['’]s|I['’]m|we['’]re|they['’]re|there['’]s|haven['’]t)\b",
     "缩略形式（学术文本里应展开）"),
    ("G15-REG-02", r"\b(kind of|sort of|pretty much|a bit|stuff|things like that|and so on|or something|a lot of)\b",
     "口语量词/模糊语"),
    ("G15-REG-03", r"\b(really|just|actually|basically|pretty)\b",
     "口语强调副词"),
    ("G15-LEX-01", r"\b(got|gets|getting)\b",
     "get 系口语动词（该用 obtain/receive/become）"),
    ("G15-LEX-02", r"\b(make|made|do|did|take|took|give|gave)\s+(a|an|the)\s+\w{3,}(tion|ment|ance|ence)\b",
     "轻动词 + 名词化（make an improvement）"),
    ("G15-LEX-03", r"\b(big|good|bad|nice)\s+(problem|issue|thing|idea|change|effect)\b",
     "高频泛化形容词代精确词"),
]

MARKER_SETS = {"zh": ZH_MARKERS, "g15": GEN15_MARKERS}

# ----------------------------------------------------------------------------
# 「反过度编辑」轴 —— 2026-10-23 用一份 46% 被判 AI 的真实硕士论文标的。
# ⚠️ 这三组阈值只有**一个案例**支撑，未用人类学术语料校准。只作 INFO，不判红。
# 案例实测：句首 the 占 23.9% / 立场标记 0.2 每千词 / 第一人称 0 / 段长 cv 0.35
# ----------------------------------------------------------------------------
STANCE = (r"\b(surprisingly|counterintuitively|importantly|notably|interestingly|arguably|"
          r"to be clear|in short|put differently|that said|more to the point|"
          r"the key point|what matters here|it is worth|one might)\b")
HEDGE = (r"\b(may|might|could|possibly|perhaps|likely|unlikely|appears?|suggests?|seems?|"
         r"plausibl[ey]|presumably|tentative(ly)?|roughly|approximately)\b")
META = (r"\b(this section|this subsection|this chapter|as noted above|as discussed|"
        r"in what follows|the remainder of this|section \d+(\.\d+)?)\b")
ART_START = {"the", "this", "these", "that", "those", "it", "such"}

# 第一人称密度（真人学术写作通常 8–20 / 千词；纯 AI 学术体常 <3）
FIRST_PERSON = r"\b(I|we|my|our|me|us|myself|ourselves)\b"

ABBREV = {
    "e.g", "i.e", "et al", "etc", "vs", "fig", "figs", "dr", "mr", "mrs", "ms",
    "prof", "no", "pp", "p", "vol", "cf", "al", "approx", "dept", "univ", "st",
    "jr", "sr", "inc", "ltd", "co", "eq", "ref", "refs", "sec", "ch", "tab",
}


# ----------------------------------------------------------------------------
# 基础解析
# ----------------------------------------------------------------------------

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def clean(raw: str) -> str:
    t = raw.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)          # markdown 标题
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)                 # 粗体
    t = re.sub(r"`{1,3}", "", t)
    t = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", t)              # 链接
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def split_sentences(text: str) -> list[str]:
    """按句末标点切句，合并缩写与小数造成的假切分。"""
    flat = re.sub(r"[ \t]+", " ", text.replace("\n", " "))
    parts = re.split(r"(?<=[.!?])[\"')\]]?\s+(?=[\"'(\[]?[A-Z0-9])", flat)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if out:
            tail = out[-1].rstrip(" .").split(" ")[-1].lower().strip(".,")
            if tail in ABBREV or re.fullmatch(r"\d+", tail):
                out[-1] = out[-1] + " " + p
                continue
        out.append(p)
    return [s for s in out if word_count(s) >= 2]


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", text)


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def per_k(count: int, words: int) -> float:
    return round(count / words * 1000, 1) if words else 0.0


# ----------------------------------------------------------------------------
# 度量
# ----------------------------------------------------------------------------

def measure(text: str, marker_set: str = "zh") -> dict:
    flat = re.sub(r"[ \t]+", " ", text.replace("\n", " "))
    sents = split_sentences(text)
    lens = [word_count(s) for s in sents]
    toks = tokens(text)
    wc = word_count(text)
    low = flat.lower()

    m: dict = {}
    m["words"] = wc
    m["sentences"] = len(sents)
    m["paragraphs"] = len([p for p in re.split(r"\n\s*\n", text) if word_count(p) > 8])

    if lens:
        m["sent_mean"] = round(st.mean(lens), 1)
        m["sent_sd"] = round(st.pstdev(lens), 1) if len(lens) > 1 else 0.0
        m["sent_cv"] = round(m["sent_sd"] / m["sent_mean"], 3) if m["sent_mean"] else 0.0
        m["sent_min"], m["sent_max"] = min(lens), max(lens)
        m["short_ratio"] = round(sum(1 for x in lens if x <= 10) / len(lens), 3)
        m["long_ratio"] = round(sum(1 for x in lens if x >= 28) / len(lens), 3)
        run = cur = 1
        for a, b in zip(lens, lens[1:]):
            cur = cur + 1 if abs(a - b) < 5 else 1
            run = max(run, cur)
        m["uniform_run"] = run
        m["sentence_lengths"] = lens
    else:
        for k in ("sent_mean", "sent_sd", "sent_cv", "sent_min", "sent_max",
                  "short_ratio", "long_ratio", "uniform_run"):
            m[k] = 0
        m["sentence_lengths"] = []

    # TTR 与文本长度强相关，短文本不可比 ⇒ 只在 ≥300 词时给值，且只作参考不进闸门
    m["ttr_300"] = None
    if len(toks) >= 300:
        win = [t.lower() for t in toks[:300]]
        m["ttr_300"] = round(len(set(win)) / len(win), 3)

    ai_set = set(AI_WORDS)
    hits = [t for t in toks if t.lower() in ai_set]
    m["ai_words"] = sorted({t.lower() for t in hits})
    m["ai_word_hits"] = len(hits)
    m["ai_word_per_1k"] = per_k(len(hits), wc)

    ph = []
    for pat in AI_PHRASES:
        for hit in re.finditer(pat, low):
            ph.append(hit.group(0)[:48])
    m["ai_phrases"] = ph

    conn = []
    for c in AI_CONNECTORS:
        n = len(re.findall(r"(?<!\w)" + re.escape(c) + r"(?!\w)", low))
        if n:
            conn.append((c, n))
    m["connectors"] = conn
    m["connector_total"] = sum(n for _, n in conn)
    m["connector_per_1k"] = per_k(m["connector_total"], wc)

    mk = []
    for mid, pat, desc in MARKER_SETS[marker_set]:
        hits = re.findall(pat, flat, flags=re.I)
        if hits:
            mk.append({"id": mid, "desc": desc, "count": len(hits)})
    m["l1_markers"] = mk
    m["l1_marker_total"] = sum(x["count"] for x in mk)
    m["l1_marker_per_1k"] = per_k(m["l1_marker_total"], wc)
    m["l1_marker_types"] = len(mk)

    m["fp_per_1k"] = per_k(len(re.findall(FIRST_PERSON, text)), wc)
    # 只数「当标点用」的破折号。U+2014 一律算；U+2013 只有前后带空格才算——
    # 否则 2021–2024 / manager–firm / exposure–log-weight 这些连接号会被误判成 AI tell。
    m["em_dash"] = (len(re.findall("\u2014", text))
                    + len(re.findall(r"(?<=\s)\u2013(?=\s)", text)))
    m["semicolon"] = text.count(";")
    m["colon"] = len(re.findall(r"(?<!\d):(?!\d)", text))

    # ── 反过度编辑轴 ──
    LEAD = "\"'([{\u2018\u201c\u300c"
    fw = []
    for x in sents:
        parts = x.split()
        if not parts:
            continue
        w = parts[0]
        while w and w[0] in LEAD:
            w = w[1:]
        if w:
            fw.append(w.lower())
    if fw:
        cnt = collections.Counter(fw)
        top_w, top_n = cnt.most_common(1)[0]
        m["sent_init_top_word"] = top_w
        m["sent_init_top_share"] = round(top_n / len(fw), 3)
        m["sent_init_types"] = len(cnt)
        m["sent_init_type_ratio"] = round(len(cnt) / len(fw), 3)
        m["sent_init_article_share"] = round(
            sum(1 for w in fw if w in ART_START) / len(fw), 3)
    else:
        m["sent_init_top_word"] = "-"
        m["sent_init_top_share"] = m["sent_init_type_ratio"] = 0
        m["sent_init_types"] = m["sent_init_article_share"] = 0

    m["stance_per_1k"] = per_k(len(re.findall(STANCE, text, re.I)), wc)
    m["hedge_per_1k"] = per_k(len(re.findall(HEDGE, text, re.I)), wc)
    m["meta_per_1k"] = per_k(len(re.findall(META, text, re.I)), wc)

    # 段长变异：只滤掉表格单元/项目符号碎片（<15 词），不滤短段——
    # 短段本身就是节奏的一部分，滤掉会把"段落长短不齐"这个信号抹平。
    paras = [p for p in re.split(r"\n\s*\n", text) if word_count(p) >= 15]
    if len(paras) >= 3:
        pl = [word_count(p) for p in paras]
        m["paragraph_cv"] = round(st.pstdev(pl) / st.mean(pl), 3) if st.mean(pl) else 0.0
    else:
        m["paragraph_cv"] = None

    # 连续三句长度接近 ⇒ 节奏平板。
    # ⚠️ 原始计数会随文本变长而膨胀（9k 词必然比 200 词攒得多），不能用绝对阈值。
    # 改成「占窗口的比例」，再跟同长度同方差的随机序列比，得到 flat_excess。
    flat_spans = 0
    if len(lens) >= 3:
        for i in range(len(lens) - 2):
            w = lens[i:i + 3]
            if max(w) - min(w) < 5:
                flat_spans += 1
    m["flat_triplets"] = flat_spans
    if len(lens) >= 20:
        win = len(lens) - 2
        m["flat_share"] = round(flat_spans / win, 3)
        mu, sd = st.mean(lens), st.pstdev(lens)
        rng = random.Random(20261023)          # 固定种子，结果可复现
        base_hits = 0
        base_tot = 0
        for _ in range(200):
            sim = [max(1, round(rng.gauss(mu, sd))) for _ in range(len(lens))]
            for i in range(len(sim) - 2):
                w = sim[i:i + 3]
                if max(w) - min(w) < 5:
                    base_hits += 1
            base_tot += len(sim) - 2
        m["flat_base"] = round(base_hits / base_tot, 3)
        m["flat_excess"] = round(m["flat_share"] / m["flat_base"], 2) if m["flat_base"] else None
    else:
        m["flat_share"] = m["flat_base"] = m["flat_excess"] = None
    return m


# ----------------------------------------------------------------------------
# 判定 —— 工程默认线，⛔ 不是文献值
# ----------------------------------------------------------------------------
# 文体决定句法目标：学术体裁天生低意外度，不能拿口语线去要求它。
GENRE = {
    "academic": {
        "sent_mean": (16, 26),
        "sent_cv": (0.36, 0.85),
        "short_ratio": (0.07, 0.22),
        "long_ratio": (0.12, 0.34),
        "uniform_run": (0, 2),
        "connector_per_1k": (0, 12),
        "fp_per_1k": (2, 20),
        "ai_word_per_1k": (0, 3),
        "em_dash": (0, 0),
        "flat_excess": (0, 1.8),
        # 过度编辑轴：文本越"匀"，检测器越确定。这三项是被判 AI 的常客。
        "sent_init_top_share": (0, 0.16),
        "sent_init_article_share": (0, 0.24),
        "sent_init_type_ratio": (0.45, 1.00),
        "paragraph_cv": (0.45, 1.60),
    },
    "post": {   # discussion post / 邮件 / 申请文书
        "sent_mean": (10, 20),
        "sent_cv": (0.42, 1.00),
        "short_ratio": (0.14, 0.34),
        "long_ratio": (0.06, 0.26),
        "uniform_run": (0, 2),
        "connector_per_1k": (0, 8),
        "fp_per_1k": (6, 40),
        "ai_word_per_1k": (0, 2),
        "em_dash": (0, 0),
        "flat_excess": (0, 1.8),
        "sent_init_top_share": (0, 0.20),
        "sent_init_article_share": (0, 0.28),
        "sent_init_type_ratio": (0.45, 1.00),
        "paragraph_cv": (0.38, 1.60),
    },
}

# 水平档决定「能容忍几处母语标记」。论文里密度过高不是「像人」，是「语言有问题」。
BAND = {
    "6.0": {"l1_marker_per_1k": (8, 16), "l1_marker_types": (3, 4)},
    "6.5": {"l1_marker_per_1k": (6, 12), "l1_marker_types": (2, 4)},
    "7.0": {"l1_marker_per_1k": (3, 8), "l1_marker_types": (2, 3)},
    "7.5": {"l1_marker_per_1k": (1, 5), "l1_marker_types": (1, 2)},
    # 到达年龄 ≥12 的 Gen 1.5：语法基本干净，痕迹是语域泄漏，密度必须低
    "g15": {"l1_marker_per_1k": (1, 4), "l1_marker_types": (1, 2)},
}

ALWAYS = {"ai_phrases": (0, 0)}   # 短语级 AI tell 一律归零，不分文体
UPPER_ONLY = {"ai_word_per_1k", "ai_phrases", "em_dash", "flat_excess",
              "uniform_run", "connector_per_1k",
              "sent_init_top_share", "sent_init_article_share"}

# ⚠️ 弱代理：只打印参考值，不判红。这三项在不同文体/不同人之间差异极大，
# 拿它当闸门会把好文本判死。有校准样本时以样本值为准。
SOFT = {"sent_mean", "short_ratio", "long_ratio", "sent_init_type_ratio"}


def targets(genre: str, band: str) -> dict:
    t = dict(GENRE[genre])
    t.update(BAND[band])
    t.update(ALWAYS)
    return t


def verdict(m: dict, genre: str = "academic", band: str = "7.0",
            manual_markers: int = 0) -> list[tuple[str, str, str]]:
    rows = []
    for k, (lo, hi) in targets(genre, band).items():
        v = len(m["ai_phrases"]) if k == "ai_phrases" else m.get(k)
        if k == "l1_marker_per_1k" and manual_markers:
            v = round(m["l1_marker_per_1k"] + per_k(manual_markers, m["words"]), 1)
        if k == "l1_marker_types" and manual_markers:
            v = m["l1_marker_types"] + 1
        if v is None:
            why = ("SKIP 段数不足 3，cv 不可靠" if k == "paragraph_cv"
                   else "SKIP 文本太短，不计")
            rows.append((k, "n/a", why))
            continue
        if k in SOFT:
            rows.append((k, f"{v}", f"INFO 参考 {lo}–{hi}（弱代理，不判红）"))
            continue
        ok = (v <= hi) if k in UPPER_ONLY else (lo <= v <= hi)
        tag = "OK  " if ok else ("LOW " if v < lo else "HIGH")
        rows.append((k, f"{v}", f"{tag} 目标 {lo}–{hi}"))
    return rows


# ----------------------------------------------------------------------------
# 报告
# ----------------------------------------------------------------------------

def report_single(path: str, m: dict, genre: str, band: str,
                  manual: int = 0, mset: str = "zh") -> None:
    print(f"\n=== {os.path.basename(path)} ===")
    print(f"词数 {m['words']} | 句数 {m['sentences']} | 段数 {m['paragraphs']} | 文体 {genre} / 档 {band} / 指纹库 {mset}")
    if m["words"] < 200:
        print("⚠️ 文本 <200 词，句长统计不可靠。统计检测器在这个长度上也基本没有判别力。")
    print(f"句长 均值 {m['sent_mean']} / 标准差 {m['sent_sd']} / 变异系数 {m['sent_cv']} / 范围 {m['sent_min']}-{m['sent_max']}")
    fe = m.get("flat_excess")
    print(f"短句占比 {m['short_ratio']:.0%} | 长句占比 {m['long_ratio']:.0%} | 最长同长连跑 {m['uniform_run']} 句 "
          f"| 平板三连 {m['flat_triplets']}"
          + (f"（{m['flat_share']:.1%}，随机基线 {m['flat_base']:.1%}，超标 {fe}×）" if fe else ""))
    ttr = m["ttr_300"] if m["ttr_300"] is not None else "样本过短不计"
    print(f"TTR(前300词) {ttr} | 连接词 {m['connector_per_1k']}/千词 | 第一人称 {m['fp_per_1k']}/千词")
    print(f"标点 破折号 {m['em_dash']} | 分号 {m['semicolon']} | 冒号 {m['colon']}")
    print(f"\nAI 词 {m['ai_word_per_1k']}/千词：{', '.join(m['ai_words'][:18]) or '—'}")
    print(f"AI 短语命中 {len(m['ai_phrases'])}：{'; '.join(m['ai_phrases'][:8]) or '—'}")
    print(f"连接词分布：{'; '.join(f'{a}×{b}' for a, b in m['connectors']) or '—'}")
    print(f"\n母语标记 {m['l1_marker_total']} 处 / {m['l1_marker_per_1k']} 每千词 / {m['l1_marker_types']} 类"
          + (f"  ＋人工 {manual} 处" if manual else ""))
    for x in m["l1_markers"]:
        print(f"  [{x['id']}] ×{x['count']}  {x['desc']}")
    if not manual:
        print("  ⚠️ 冠词漏用 / 语域滑落 这类正则查不出来，必须人工数，用 --manual-markers N 计入")

    top = m.get("sent_init_top_word", "-")
    print(f"\n过度编辑轴（判 AI 的主战场）：")
    print(f"  句首最频词 '{top}' 占 {m.get('sent_init_top_share', 0):.1%}"
          f" | 冠词/指示词起句 {m.get('sent_init_article_share', 0):.1%}"
          f" | 句首词种类 {m.get('sent_init_types', 0)}（占比 {m.get('sent_init_type_ratio', 0):.2f}）")
    pcv = m.get("paragraph_cv")
    print(f"  段长 cv {pcv if pcv is not None else 'n/a'} | 立场 {m.get('stance_per_1k', 0)}/千词"
          f" | hedge {m.get('hedge_per_1k', 0)}/千词 | 元话语 {m.get('meta_per_1k', 0)}/千词")
    print("  ⓘ 立场/元话语不设闸门（有些文体本该零立场），只作参考：提到作者判断、用 I/we 表态度、"
          "点明「本文在做什么」都算。")

    print("\n--- 闸门 ---")
    for k, v, tag in verdict(m, genre, band, manual):
        print(f"  {k:24s} {v:>8s}   {tag}")


def profile(samples: list[str], marker_set: str = "zh") -> dict:
    ms = [measure(clean(read_text(p)), marker_set) for p in samples]
    ms = [x for x in ms if x["words"] >= 120]
    if not ms:
        raise SystemExit("样本都太短（<120 词），无法提取人格。")

    def q(key):
        vals = [x[key] for x in ms if x.get(key) is not None]
        if not vals:
            return None
        return {
            "median": round(st.median(vals), 3),
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
        }

    agg = {k: q(k) for k in ("sent_mean", "sent_sd", "sent_cv", "short_ratio",
                             "long_ratio", "connector_per_1k", "fp_per_1k",
                             "sent_init_top_share", "sent_init_article_share",
                             "sent_init_type_ratio", "stance_per_1k",
                             "hedge_per_1k", "meta_per_1k", "paragraph_cv")}
    agg = {k: v for k, v in agg.items() if v is not None}

    counts: dict[str, int] = {}
    descs: dict[str, str] = {}
    total_words = sum(x["words"] for x in ms)
    for x in ms:
        for mk in x["l1_markers"]:
            counts[mk["id"]] = counts.get(mk["id"], 0) + mk["count"]
            descs[mk["id"]] = mk["desc"]

    markers = []
    for mid, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        markers.append({
            "id": mid,
            "desc": descs[mid],
            "count": c,
            "per_1k": per_k(c, total_words),
            "papers_seen_in": sum(1 for x in ms if any(y["id"] == mid for y in x["l1_markers"])),
        })

    return {
        "source": "calibrated",
        "n_samples": len(ms),
        "total_words": total_words,
        "metrics": agg,
        "markers": markers,
        "ai_tells_in_own_work": sorted({w for x in ms for w in x["ai_words"]}),
    }


def report_profile(p: dict) -> None:
    print(f"\n=== 人格提取（{p['n_samples']} 篇 / {p['total_words']} 词）===")
    for k, v in p["metrics"].items():
        print(f"  {k:22s} 中位 {v['median']:<8} 区间 {v['min']}–{v['max']}")
    print(f"\n你自己的母语标记（按频次）：")
    if not p["markers"]:
        print("  ⚠️ 一个都没命中。可能你的英文已经很接近母语者，"
              "也可能样本太正式。→ 把 markers 收敛到 1–2 类，密度压到 3–5/千词。")
    for mk in p["markers"]:
        print(f"  [{mk['id']}] {mk['count']:>3} 次 | {mk['per_1k']:>5}/千词 | "
              f"出现在 {mk['papers_seen_in']}/{p['n_samples']} 篇 | {mk['desc']}")
    if p["ai_tells_in_own_work"]:
        print(f"\n⛔ 你自己的旧文里也有 AI 词：{', '.join(p['ai_tells_in_own_work'][:20])}")
        print("   → 这些不要写进 persona，要在改写时删掉。")
    print("\n⚠️ 脚本只能量句法/词汇/密度。**你本人特有的错法必须人工看样本标注**，"
          "脚本查不出来（比如'该用 the 的地方漏了'）。")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="L2 voice metrics")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="单篇体检")
    g.add_argument("--samples", help="旧作文目录或逗号分隔的文件列表")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--genre", choices=list(GENRE), default="academic",
                    help="文体：academic（论文/报告，默认）或 post（帖子/邮件/文书）")
    ap.add_argument("--band", choices=list(BAND), default="7.0",
                    help="水平档：6.0/6.5/7.0/7.5 走中文迁移指纹；g15 走 ear learner 指纹")
    ap.add_argument("--markers", choices=list(MARKER_SETS), default=None,
                    help="指纹库；不填则按 band 自动选（g15→g15，其余→zh）")
    ap.add_argument("--manual-markers", type=int, default=0, metavar="N",
                    help="人工数出的、正则查不到的母语标记数（如冠词漏用），计入闸门")
    a = ap.parse_args()
    mset = a.markers or ("g15" if a.band == "g15" else "zh")

    if a.text:
        m = measure(clean(read_text(a.text)), mset)
        if a.json:
            print(json.dumps(m, ensure_ascii=False, indent=2))
        else:
            report_single(a.text, m, a.genre, a.band, a.manual_markers, mset)
        return

    pats = [s.strip() for s in a.samples.split(",")] if "," in a.samples else None
    files = pats or sorted(
        f for ext in ("*.txt", "*.md")
        for f in glob.glob(os.path.join(a.samples, ext))
    )
    if not files:
        raise SystemExit(f"没找到 .txt/.md 文件：{a.samples}")
    p = profile(files, mset)
    if a.json:
        print(json.dumps(p, ensure_ascii=False, indent=2))
    else:
        report_profile(p)


if __name__ == "__main__":
    main()
