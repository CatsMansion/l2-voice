#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""intake —— 英语学习路径量表。输入经历，输出该用哪个档、主短板在哪。

用法：
  python intake.py --template          # 生成 answers.json 骨架
  python intake.py --answers a.json    # 打分
  python intake.py --ask               # 交互式逐题问
  python intake.py --answers a.json --md   # 直接输出 persona card 草稿

⚠️ 定位：这是**先验**，不是测量。它的作用是「在你还没给文本时，先选对配置」。
   给了文本以后，一律以 l2metrics.py 的实测值为准，本量表的结论作废。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ----------------------------------------------------------------------------
# 题库
# ----------------------------------------------------------------------------
# 每题：id / 问法 / 选项 / 说明（为什么问这个）
Q = [
    ("english_start_age", "你几岁开始系统学英语（学校课程或补习）？",
     ["6 岁前", "7-9 岁", "10-12 岁", "13 岁后"], 0,
     "起点年龄决定你有没有靠语法书打底（eye learner 的底色）"),

    ("arrival_age", "你几岁到英语国家长期读书（超过 1 年）？",
     ["没去过（只短期）", "12 岁前", "12-15 岁", "16-18 岁", "18 岁后（只读研/本科后段）"], 3,
     "到达年龄 12 岁是研究里的分界线，不是「来了几年」"),

    ("years_in_country", "到现在为止在英语国家累计待了几年？",
     ["<2 年", "2-4 年", "4-6 年", "6-9 年", "9 年以上"], 3,
     "居住时长单独预测力很弱，要和到达年龄一起看"),

    ("highest_stage", "你在英语国家读完的最高阶段是？",
     ["没读过", "语言班/预科", "中学", "本科", "研究生"], 3,
     "在哪个阶段读完，决定你的学术语篇是在哪套体系里学的"),

    ("reading_pages", "现在每周读英文学术文本（论文/教材/专著）多少页？",
     ["<10 页", "10-30 页", "30-60 页", ">60 页"], 1,
     "二语阅读理解与写作成绩相关 r=.588（meta 分析），是阅读→写作最强的单一桥梁"),

    ("long_papers", "过去三年你交过多少篇 ≥2000 词的英文，且有评分和批注？",
     ["0 篇", "1-3 篇", "4-8 篇", "9 篇以上"], 1,
     "有反馈的输出量。没有反馈的写作不产生语域进步"),

    ("writing_process", "你写英文段落时，脑子里通常怎么走？",
     ["几乎总是先想中文再翻", "经常先想中文", "一半一半", "基本直接用英文组织"], 2,
     "翻译式产出 ⇒ 母语迁移痕迹明显（zh 档）；直接产出 ⇒ 迁移少（g15 档）"),

    ("grammar_instruction", "你系统学过英语语法（从句、时态体系、冠词规则）吗？",
     ["系统学过，能讲规则", "学过一些", "基本靠语感"], 1,
     "eye learner 的判据。系统学过 ⇒ 会犯的错不一样（偏语序和搭配，不偏屈折词素）"),

    ("feedback", "有人逐句批注过你的英文吗？",
     ["从来没有", "1-2 门课有过", "经常有"], 1,
     "逐句批注是 academic register 最直接的输入渠道"),

    ("issues", "你读自己写的东西时，能看出下面哪些问题？（可多选）",
     ["冠词 the/a 用不准", "介词搭配不对", "虽然但是 / 因为所以 双连词",
      "口语词混进论文（a lot of / a bit / get）", "时态不一致",
      "句子结构太像模板", "以上都看不出"], [], 
     "自评是可用的：LEAP-Q 验证过自报与实测有稳定关系；且「能看出什么」比「觉得自己几分」准得多"),

    ("discipline", "你的专业属于？",
     ["人文/社科", "理工/医学", "商科/法律", "艺术/设计"], 0,
     "决定第一人称、hedging 的预期，以及能不能用 I argue"),

    ("uses_firstly", "你写论文会用 Firstly / Secondly / Thirdly 吗？",
     ["几乎每篇都用", "有时用", "基本不用"], 1,
     "序数标记密度是模板化的直接指标"),

    ("uses_in_conclusion", "你写论文会用 In conclusion / To sum up 收尾吗？",
     ["几乎每篇都用", "有时用", "基本不用"], 1,
     "同上。这两题是 template 风险的自报代理"),

    ("perceived_template", "有人说过你的英文「写得像模板 / 太规整」吗？",
     ["有", "没有", "不确定"], 2,
     "外部反馈，权重高于自评"),

    ("ielts", "你的 IELTS / TOEFL 成绩（没有就留空）",
     None, "",
     "只作交叉校验，⛔ 不作为选档依据——它测不出学术语域"),
]

FIELDS = {q[0]: q for q in Q}

# 自评问题 → 指纹候选
ISSUE_MAP = {
    "冠词 the/a 用不准": ("zh", "ZH-ART-A1"),
    "介词搭配不对": ("zh", "ZH-PREP-C1"),
    "虽然但是 / 因为所以 双连词": ("zh", "ZH-CONJ-D1"),
    "口语词混进论文（a lot of / a bit / get）": ("g15", "G15-REG-02"),
    "时态不一致": ("g15", "G15-INF-01"),
    "句子结构太像模板": ("both", "TEMPLATE"),
}


# ----------------------------------------------------------------------------
# 打分
# ----------------------------------------------------------------------------

def _stage_idx(v: str) -> int:
    return ["没读过", "语言班/预科", "中学", "本科", "研究生"].index(v) if v else -1


def _arrival_idx(v: str) -> int:
    return ["没去过（只短期）", "12 岁前", "12-15 岁", "16-18 岁", "18 岁后（只读研/本科后段）"].index(v)


def _ord(v: str, opts: list) -> int:
    return opts.index(v) if v in opts else 0


def score(a: dict) -> dict:
    fired, conflicts = [], []
    out = {
        "marker_set": None, "script_band": None,
        "proficiency": None, "main_failure": None,
        "marker_candidates": [], "expected_direction": {},
    }

    def setk(k, v, rule, why, conf):
        if out.get(k) not in (None, v):
            conflicts.append(f"{k}：{rule} 想设 {v}，但已被设为 {out[k]}")
            return
        out[k] = v
        fired.append({"rule": rule, "set": f"{k}={v}", "why": why, "conf": conf})

    ARR_OPTS = FIELDS["arrival_age"][2]
    arr = _ord(a.get("arrival_age") or "", ARR_OPTS) if a.get("arrival_age") in ARR_OPTS else 3
    stage = _stage_idx(a.get("highest_stage") or "本科")
    wp = a.get("writing_process") or ""
    proc = "translate" if "中文" in wp and "一半" not in wp else ("mixed" if "一半" in wp else "direct")

    # R1 到达年龄 <12 ⇒ 写作接近母语者
    if arr == 1:
        setk("marker_set", "g15", "R1",
             "12 岁前到达：研究显示写作接近单语母语者（de Kleine et al. 2024）", 0.9)
        setk("script_band", "g15", "R1", "同上；标记密度应取 0–2/千词", 0.85)
        setk("proficiency", "C2", "R1", "早期到达 + 长期居住", 0.7)

    # R2 12–18 岁到达、且在英语国家读完中学 ⇒ g15（ear learner）
    elif arr in (2, 3) and stage >= 2:
        setk("marker_set", "g15", "R2",
             "12–18 岁到达且在英语国家读完中学 ⇒ ear learner 型，保留残余痕迹（de Kleine 2024；Reid 1998）", 0.9)
        setk("script_band", "g15", "R2", "用 g15 指纹库，⛔ 不要套中文迁移配方", 0.9)

    # R2b 矛盾：中学年龄到达但没在那里读完中学
    elif arr in (2, 3):
        conflicts.append("到达年龄是中学阶段，但「在英语国家读完的最高阶段」低于中学 ⇒ "
                         "需要确认到底在当地读了几年书（这个答案决定用哪个指纹库）")
        setk("marker_set", "zh", "R2b", "学术英语主要在中文体系完成，按迁移型处理", 0.5)

    # R3 18 岁后才出国 / 没出国 ⇒ 中文迁移型
    else:
        setk("marker_set", "zh", "R3",
             "18 岁后才出国或没出国 ⇒ 学术英语在中文体系学完，母语迁移痕迹明显", 0.85)

    # R4 翻译式产出 ⇒ 迁移痕迹重
    if proc == "translate" and out["marker_set"] == "g15":
        conflicts.append("writing_process=先想中文再翻 与 marker_set=g15 冲突："
                         "翻译式产出通常伴随母语迁移痕迹，建议采样确认")
    if proc == "translate":
        fired.append({"rule": "R4", "set": "transfer_risk=high",
                      "why": "先想中文再翻 ⇒ 语序/搭配类迁移痕迹概率高", "conf": 0.7})

    # 学术强度：有反馈的学术阅读 × 有反馈的输出
    read_i = _ord(a.get("reading_pages") or "<10 页", FIELDS["reading_pages"][2])
    paper_i = _ord(a.get("long_papers") or "0 篇", FIELDS["long_papers"][2])
    calp = read_i + paper_i   # 0-6

    if calp <= 1:
        setk("main_failure", "vocabulary", "R5",
             "学术阅读少 + 有反馈输出少 ⇒ 学术词汇量与语域都没建立（词汇量与写作 r=.481–.525）", 0.75)
        setk("proficiency", "B2+", "R5", "输入输出双低", 0.6)
    elif proc == "translate":
        setk("main_failure", "transfer", "R6",
             "产出仍走翻译路径 ⇒ 短板在句法迁移，不在词汇或语域", 0.7)
        setk("proficiency", "C1", "R6", "输入够、产出路径迂回", 0.55)
    elif calp <= 3:
        setk("main_failure", "register", "R7",
             "输入或输出有一端不足 ⇒ 典型短板是语域（口语体漏进学术文本）", 0.7)
        setk("proficiency", "C1", "R7", "单端不足", 0.6)
    else:
        setk("main_failure", "template", "R8",
             "阅读与有反馈输出都够 + 直接用英文写 ⇒ 语法不再是瓶颈，剩下的是语篇模板化", 0.65)
        setk("proficiency", "C1+", "R8", "双端够 + 直接产出", 0.6)

    # R12 zh 档的密度档位由学术强度推
    if out["script_band"] is None:
        lvl = "6.0" if calp <= 1 else ("6.5" if calp <= 3 else ("7.0" if calp <= 5 else "7.5"))
        setk("script_band", lvl, "R12",
             f"学术强度指数 {calp}/6 ⇒ 中文迁移档取 {lvl}（指数越高，能容忍的母语标记越少）", 0.5)

    # 模板风险（外部反馈 > 自评）
    if a.get("perceived_template") == "有":
        fired.append({"rule": "R9", "set": "template_risk=confirmed",
                      "why": "有外部反馈说你「像模板」⇒ 这是最硬的一条，权重高于自评", "conf": 0.85})
        if out["main_failure"] not in ("vocabulary",):
            out["main_failure"] = "template"
            fired.append({"rule": "R9b", "set": "main_failure=template",
                          "why": "被 R9 覆盖：外部反馈优先", "conf": 0.8})
    seq = _ord(a.get("uses_firstly") or "有时用", FIELDS["uses_firstly"][2]) + \
          _ord(a.get("uses_in_conclusion") or "有时用", FIELDS["uses_in_conclusion"][2])
    if seq >= 3:
        fired.append({"rule": "R10", "set": "template_risk=high",
                      "why": "序数标记 + 结论套语几乎每篇都用 ⇒ 模板化的自报证据", "conf": 0.7})

    # 自评问题 → 候选标记
    for it in (a.get("issues") or []):
        if it in ISSUE_MAP:
            ms, mid = ISSUE_MAP[it]
            if ms in ("both", out["marker_set"]):
                out["marker_candidates"].append(mid)
                fired.append({"rule": "R11", "set": f"candidate+{mid}",
                              "why": f"自评承认「{it}」", "conf": 0.55})

    # 预期方向（只给方向，不给数值）
    band = out["script_band"] or "7.0"
    if out["main_failure"] == "template":
        out["expected_direction"] = {
            "connector_per_1k": "大概率偏高（>12）——模板化的直接指标",
            "sent_cv": "大概率偏低（<0.45）——句长太齐",
            "l1_marker_per_1k": "不会高——语法不是你的瓶颈",
        }
    elif out["main_failure"] == "register":
        out["expected_direction"] = {
            "connector_per_1k": "中等",
            "l1_marker_per_1k": "低但可检出",
            "fp_per_1k": "可能偏低（不爱用第一人称）",
        }
    elif out["main_failure"] == "transfer":
        out["expected_direction"] = {
            "l1_marker_per_1k": "偏高，且集中在介词/语序类",
            "sent_mean": "可能偏长（中文长句迁移）",
        }
    else:
        out["expected_direction"] = {
            "connector_per_1k": "高",
            "l1_marker_per_1k": "中到高",
            "ai_word_per_1k": "可能偏高（靠模板词撑学术感）",
        }

    # 置信度
    crit = ["arrival_age", "highest_stage", "reading_pages", "long_papers", "writing_process"]
    filled = sum(1 for k in crit if a.get(k))
    conf = round(min(0.45 + 0.08 * filled, 0.85), 2)
    if a.get("perceived_template") in ("有", "没有"):
        conf = round(min(conf + 0.05, 0.9), 2)

    out["confidence"] = conf
    out["fired"] = fired
    out["conflicts"] = conflicts
    out["calp_index"] = calp
    out["id"] = a.get("name") or "unnamed"
    return out


# ----------------------------------------------------------------------------
# 输出
# ----------------------------------------------------------------------------

def report(r: dict, a: dict) -> None:
    print(f"\n=== 学习路径诊断 · {r['id']} ===")
    print(f"置信度 {r['confidence']}（上限 0.85–0.9，量表本身不可能更高）\n")

    print(f"指纹库        {r['marker_set']}    → 脚本请用 --band {r['script_band']}")
    print(f"学术强度指数  {r['calp_index']}/6（阅读×输出）")
    print(f"水平估计      {r['proficiency']}（人群先验，非实测）")
    print(f"主短板        {r['main_failure']}")

    print("\n--- 命中的规则 ---")
    for f in r["fired"]:
        print(f"  [{f['rule']}] {f['set']}")
        print(f"         {f['why']}（conf {f['conf']}）")

    if r["marker_candidates"]:
        print(f"\n候选指纹：{', '.join(sorted(set(r['marker_candidates'])))}")

    print("\n--- 预期方向（只给方向，不给数值）---")
    for k, v in r["expected_direction"].items():
        print(f"  {k:20s} {v}")

    if r["conflicts"]:
        print("\n⚠️ 冲突（必须追问，不许平均掉）")
        for c in r["conflicts"]:
            print(f"  - {c}")

    print("\n--- 下一步（必须做，否则上表全是猜）---")
    print(f"  1. 拿一篇你写过的英文（≥300 词，同文体），跑：")
    print(f"       python scripts/l2metrics.py --text <文件> --band {r['script_band']}")
    print(f"  2. 把实测的 connector_per_1k / sent_cv / l1_marker_per_1k 和上面「预期方向」对比")
    print(f"  3. 对不上 ⇒ 量表的推断错了，以文本为准，并回来改 answers.json")
    print("\n⛔ 量表只解决「先选对配置」。它测不出你的水平，也测不出 AI 率。")


def to_md(r: dict, a: dict) -> str:
    return f"""# Persona Card · {r['id']}

| 项 | 值 |
|---|---|
| L1 | zh |
| 水平档 | {r['script_band']} |
| 来源 | template（⚠️ 未用文本校准） |
| 学术强度指数 | {r['calp_index']}/6 |
| 主短板 | {r['main_failure']} |
| 量表置信度 | {r['confidence']} |

## 固定弱点（⛔ 只许 1–3 类）

| # | ID | 描述 | 每千词 | 用在哪 |
|---|---|---|---|---|
{chr(10).join(f"| {i+1} | {m} | 待文本确认 | 1–4 | 全篇 |" for i, m in enumerate(sorted(set(r['marker_candidates']))[:3])) or "| — | 待文本确认 | — | — | — |"}

## 预期方向

{chr(10).join(f"- `{k}`：{v}" for k, v in r['expected_direction'].items())}

## 命中规则

{chr(10).join(f"- [{f['rule']}] {f['why']}" for f in r['fired'])}

## 待验证

- 以上全部是量表推断，⛔ 未经文本校准。给 3 篇旧作文后，本卡作废重建。
"""


def template() -> dict:
    return {
        "name": "your-name",
        "english_start_age": "",
        "arrival_age": "",
        "years_in_country": "",
        "highest_stage": "",
        "reading_pages": "",
        "long_papers": "",
        "writing_process": "",
        "grammar_instruction": "",
        "feedback": "",
        "issues": [],
        "discipline": "",
        "uses_firstly": "",
        "uses_in_conclusion": "",
        "perceived_template": "",
        "ielts": "",
        "_options": {q[0]: q[2] for q in Q if q[2]},
    }


def ask() -> dict:
    a = {"name": input("代号（随便起，用于存档）: ").strip() or "unnamed"}
    for qid, text, opts, _default, why in Q:
        print(f"\n{text}")
        if why:
            print(f"  （{why}）")
        if opts:
            for i, o in enumerate(opts, 1):
                print(f"  {i}. {o}")
            raw = input("  选择编号: ").strip()
            try:
                a[qid] = opts[int(raw) - 1]
            except Exception:
                a[qid] = ""
        else:
            a[qid] = input("  可多选，逗号分隔编号；不确定就回车: ").strip()
    return a


def main() -> None:
    ap = argparse.ArgumentParser(description="英语学习路径量表")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--template", action="store_true", help="输出 answers.json 骨架")
    g.add_argument("--answers", help="answers.json 路径")
    g.add_argument("--ask", action="store_true", help="交互式逐题问")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--md", action="store_true", help="输出 persona card 草稿")
    ap.add_argument("--write", metavar="DIR", help="把 persona card 写到指定目录")
    args = ap.parse_args()

    if args.template:
        print(json.dumps(template(), ensure_ascii=False, indent=2))
        return

    a = ask() if args.ask else json.load(open(args.answers, encoding="utf-8"))
    r = score(a)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    if args.md or args.write:
        md = to_md(r, a)
        if args.write:
            os.makedirs(args.write, exist_ok=True)
            p = os.path.join(args.write, f"{r['id']}-intake.md")
            open(p, "w", encoding="utf-8").write(md)
            print(f"已写入 {p}")
        else:
            print(md)
        return
    report(r, a)


if __name__ == "__main__":
    main()
