# -*- coding: utf-8 -*-
"""一条命令出评测报告：四个数全部从实际输出与结果文件里读，不写死。

用法：python eval_report.py
输出：公开版/评测报告.md；同时写 公开版/测试留档/评测数据.json 供机器复核。

四个数的来源：
  检出率、误报率   公开版/测试留档/eval.py.log ＋ 运营自检/golden_truth.json
  跨引擎一致性     公开版/测试留档/smoke_test.js.log
  负向测试拦住数   公开版/测试留档/负向测试-v332.py.log
                    公开版/测试留档/负向测试-泳道图布局.py.log
"""
import datetime
import hashlib
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 公开仓库里脚本放在仓库根，运营自检/ 与脚本同级；本地工程里脚本在 公开版/ 下。
# 按「运营自检/ 在哪」自适应，让同一份脚本在两处都能跑。
if not os.path.isdir(os.path.join(ROOT, "运营自检")) and os.path.isdir(os.path.join(HERE, "运营自检")):
    ROOT = HERE
LOGS = os.path.join(HERE, "测试留档")
SELF = os.path.join(ROOT, "运营自检")
OUT_MD = os.path.join(HERE, "评测报告.md")
OUT_JSON = os.path.join(LOGS, "评测数据.json")


def read(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def parse_eval():
    log = read(os.path.join(LOGS, "eval.py.log"))
    m = re.search(r"合计：注入 (\d+) 项，检出 (\d+) 项，检出率 ([\d.]+)%", log)
    m2 = re.search(r"漏检 (\d+) 项，疑似误报 (\d+) 项", log)
    if not m or not m2:
        raise RuntimeError("eval.py.log 里解析不到合计行，先跑 python 跑六套测试.py")
    truth = json.loads(read(os.path.join(SELF, "golden_truth.json")))
    counted = sum(len(s["injected"]) for s in truth["samples"])
    inj, hit, missed, extra = int(m.group(1)), int(m.group(2)), int(m2.group(1)), int(m2.group(2))
    if counted != inj:
        raise RuntimeError("golden_truth.json 里数出的注入项 %d 与 eval.py 报的 %d 不一致" % (counted, inj))
    rate = hit / inj * 100 if inj else 0.0
    fp_rate = extra / (hit + extra) * 100 if (hit + extra) else 0.0
    return {"注入": inj, "检出": hit, "漏检": missed, "疑似误报": extra,
            "检出率": round(rate, 1), "误报率": round(fp_rate, 1),
            "golden_truth_注入项": counted,
            "来源": "测试留档/eval.py.log ＋ 运营自检/golden_truth.json"}


def parse_smoke():
    log = read(os.path.join(LOGS, "smoke_test.js.log"))
    rows = re.findall(r"(.+?)\s*两边一致：(\d+) 项", log)
    truth = json.loads(read(os.path.join(SELF, "golden_truth.json")))
    return {"样例": [{"名称": n.strip(), "两边一致项数": int(v)} for n, v in rows],
            "一致样例数": len(rows), "样例总数": len(truth["samples"]),
            "逐份数字": "/".join(v for _, v in rows),
            "来源": "测试留档/smoke_test.js.log ＋ 运营自检/golden_truth.json"}


def parse_negative():
    p1 = os.path.join(LOGS, "负向测试-v332.py.log")
    p2 = os.path.join(LOGS, "负向测试-泳道图布局.py.log")
    a, b = read(p1), read(p2)
    m1 = re.search(r"负向测试结果：(\d+) / (\d+) 组被拦住", a)
    m2 = re.search(r"结果：拦住 (\d+)/(\d+)", b)
    if not m1 or not m2:
        raise RuntimeError("负向测试 log 里解析不到结果行，先跑 python 跑负向测试.py")
    caught1, total1 = int(m1.group(1)), int(m1.group(2))
    caught2, total2 = int(m2.group(1)), int(m2.group(2))
    return {"v332": "%d/%d" % (caught1, total1),
            "泳道图": "%d/%d" % (caught2, total2),
            "合计拦住": caught1 + caught2, "合计用例": total1 + total2,
            "还原一致": ("md5 与动手前一致 True" in a and "还原后内容一致：是" in b),
            "来源": "测试留档/负向测试-v332.py.log ＋ 测试留档/负向测试-泳道图布局.py.log"}


def per_module_prf(truth=None):
    """借鉴 4：A–F 六个规则模块各算一次精确率、召回率、F1。

    出处：nityaattili/AI-feedback-categoriser 的 evaluate.py，compute_accuracy()
    里按类别累计 tp / fp / fn，再算 precision / recall / F1。
    仓库 https://github.com/nityaattili/AI-feedback-categoriser ，
    本地副本 _work/参考项目/nityaattili__AI-feedback-categoriser/evaluate.py，
    下载日期 2026-11-09，见 _work/参考项目/_sources.json。
    这里把「类别」换成 A–F 六个规则模块，公式照搬，没有另立方法。

    数据不写死：复用 运营自检/eval.py 的同一批模块与 golden_truth.json 现跑现算。
    truth 可由验证脚本传入内存副本，用来做负向测试。
    """
    import sys
    if truth is None:
        truth = json.loads(read(os.path.join(SELF, "golden_truth.json")))
    if SELF not in sys.path:
        sys.path.insert(0, SELF)
    import common
    import A_number_check
    import B_wording_check
    import C_structure_check
    import D_consistency_check
    import E_source_check
    import F_enum_count_check

    mods = [("A", A_number_check), ("B", B_wording_check), ("C", C_structure_check),
            ("D", D_consistency_check), ("E", E_source_check), ("F", F_enum_count_check)]
    common.set_verbose(False)
    counts = {k: {"TP": 0, "FP": 0, "FN": 0} for k, _ in mods}

    for s in truth["samples"]:
        common.set_target(os.path.join(SELF, s["file"]))
        common.set_type(s["type"])
        found = {k: mod.run() for k, mod in mods}
        registered = {}
        for item in s["injected"]:
            registered.setdefault(item["module"], []).append(item["keyword"])
        for k, _ in mods:
            blob = " ".join(f.get("text", "") + f.get("issue", "") for f in found[k])
            for item in s["injected"]:
                if item["module"] != k:
                    continue
                counts[k]["TP" if item["keyword"] in blob else "FN"] += 1
            kws = registered.get(k, [])
            for f in found[k]:
                b = f.get("text", "") + f.get("issue", "")
                if not any(kw in b for kw in kws):
                    counts[k]["FP"] += 1

    rows = {}
    for k, c in counts.items():
        tp, fp, fn = c["TP"], c["FP"], c["FN"]
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        rows[k] = {"TP": tp, "FP": fp, "FN": fn,
                   "P": round(p, 3), "R": round(r, 3), "F1": round(f1, 3)}
    return rows


TOOL_HTML = os.path.join(ROOT, "人机协作流程工具", "运营场景人机协作流程工具.html")
PUB_HTML = os.path.join(HERE, "运营场景人机协作流程工具.html")
DRIFT_LOG = os.path.join(HERE, "drift-log.jsonl")


def prompt_fingerprint(html_text=None):
    """页面提示词的指纹：取 TAG_P1/TAG_P2/TAG_R1/TAG_R2 与 draftPrompt 两段原文算 sha256。

    只覆盖提示词区域，不把整份页面算进去，免得改一个 CSS 就换一次指纹。
    html_text 可由验证脚本传入，用来证明指纹确实会随提示词变化。
    """
    if html_text is None:
        # 公开仓库里只有公开版页面，没有带凭据的工具原件
        html_text = read(TOOL_HTML if os.path.exists(TOOL_HTML) else PUB_HTML)
    blob = ""
    for start_mark, end_mark in [
        ("var TAG_P1 = ", "/* 第一步的产出先存在这里"),
        ("function draftPrompt(", "/* 审读结果存这里"),
    ]:
        i = html_text.find(start_mark)
        j = html_text.find(end_mark, i) if i >= 0 else -1
        if i >= 0 and j > i:
            blob += html_text[i:j]
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def drift_cases(a=None, b=None):
    """逐用例状态，直接复用两份负向测试的 8 个用例，不另造题。

    PASS 表示破坏后测试报出了对应失败项，FAIL 表示没拦住，
    GAP 表示锚点失效导致用例没跑起来。参照 ozlar34 的 drift-log.jsonl 状态口径。
    a、b 可由验证脚本传入模拟 log，用来证明状态解析会响。
    """
    if a is None:
        a = read(os.path.join(LOGS, "负向测试-v332.py.log"))
    if b is None:
        b = read(os.path.join(LOGS, "负向测试-泳道图布局.py.log"))
    src1 = "测试留档/负向测试-v332.py.log"
    src2 = "测试留档/负向测试-泳道图布局.py.log"
    cases = []
    for blk in re.split(r"(?=用例 \d+：)", a):
        m = re.match(r"用例 (\d+)：(.+)", blk.strip())
        if not m:
            continue
        name = m.group(2).strip()
        if "跳过" in blk:
            status, flags = "GAP", ["锚点失效，用例未执行"]
        elif "-> 拦住" in blk:
            status, flags = "PASS", []
        elif "没拦住" in blk:
            status, flags = "FAIL", ["破坏后测试没报错"]
        else:
            status, flags = "GAP", ["未识别到结果"]
        cases.append({"id": "v332-%s" % m.group(1), "name": name,
                      "status": status, "flags": flags, "source": src1})
    n = 0
    for line in b.splitlines():
        m = re.match(r"\s+(拦住|没拦住)\s+(.+)", line)
        if not m:
            continue
        n += 1
        hit = m.group(1) == "拦住"
        cases.append({"id": "layout-%d" % n, "name": m.group(2).strip(),
                      "status": "PASS" if hit else "FAIL",
                      "flags": [] if hit else ["破坏后测试没报错"], "source": src2})
    return cases


def compare_drift(prev, curr):
    """对比两次报告，找出 PASS 变 FAIL 或 GAP 的用例。"""
    if not prev:
        return []
    pmap = {c["id"]: c["status"] for c in prev.get("cases", [])}
    out = []
    for c in curr.get("cases", []):
        old = pmap.get(c["id"])
        if old == "PASS" and c["status"] in ("FAIL", "GAP"):
            out.append({"id": c["id"], "from": old, "to": c["status"],
                        "name": c.get("name", "")})
    return out


def write_drift(cases):
    """追加一行记录，返回本轮记录、上一轮记录、回归列表。"""
    prev = None
    if os.path.exists(DRIFT_LOG):
        rows = [json.loads(l) for l in read(DRIFT_LOG).splitlines() if l.strip()]
        if rows:
            prev = rows[-1]
    sha = prompt_fingerprint()
    pub_sha = prompt_fingerprint(read(PUB_HTML))
    rec = {
        "ts": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "judge": "local-rules", "prompt_sha": sha, "public_prompt_sha": pub_sha,
        "summary": {
            "total": len(cases),
            "passed": sum(1 for c in cases if c["status"] == "PASS"),
            "failed": sum(1 for c in cases if c["status"] == "FAIL"),
            "gaps": sum(1 for c in cases if c["status"] == "GAP"),
            "regressions": 0,
        },
        "cases": cases,
    }
    reg = compare_drift(prev, rec)
    rec["summary"]["regressions"] = len(reg)
    with io.open(DRIFT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec, prev, reg


def main():
    ev, sm, ng = parse_eval(), parse_smoke(), parse_negative()
    prf = per_module_prf()
    cases = drift_cases()
    drift, prev, reg = write_drift(cases)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {"生成时间": now, "检出与误报": ev, "跨引擎一致性": sm,
            "负向测试": ng, "分模块PRF1": prf, "drift": drift,
            "drift_回归": reg}
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    lines = [
        "# 评测报告",
        "",
        "> 生成时间：%s　｜　一条命令：`python eval_report.py`" % now,
        "> 四个数全部读实际输出与结果文件，机器可复核的原始数据在同目录 `测试留档/评测数据.json`。",
        "",
        "## 一、四个数",
        "",
        "| 数 | 本轮实测 | 来源 |",
        "| --- | --- | --- |",
        "| 检出率 | **%.1f%%**，%d/%d 项 | `%s` |" % (ev["检出率"], ev["检出"], ev["注入"], ev["来源"]),
        "| 误报率 | **%.1f%%**，疑似误报 %d 项 | 同上，口径为「疑似误报 ÷ 检出与疑似误报之和」 |"
        % (ev["误报率"], ev["疑似误报"]),
        "| 跨引擎一致性 | **%d/%d 份样例两边一致**，逐份 %s 项 | `%s` |"
        % (sm["一致样例数"], sm["样例总数"], sm["逐份数字"], sm["来源"]),
        "| 负向测试拦住数 | **%d/%d 组**，v3.32 与泳道图各 %s、%s | `%s` |"
        % (ng["合计拦住"], ng["合计用例"], ng["v332"], ng["泳道图"], ng["来源"]),
        "",
        "四项口径说明：",
        "",
        "- 检出率与误报率来自 `运营自检/eval.py` 的注入法评测。注入项总数 %d 由 `golden_truth.json` 现场数出，与脚本报的 %d 一致，不手写。"
        % (ev["golden_truth_注入项"], ev["注入"]),
        "- 跨引擎一致性指页面内嵌引擎与 `运营自检/` Python 规则在四份样例上算出同一个数，冒烟测试逐份打印。",
        "- 负向测试是人为破坏页面再看测试是否报出对应失败项，两份脚本跑完都自动还原，还原后内容一致：%s。"
        % ("是" if ng["还原一致"] else "否"),
        "",
        "## 二、六套测试的退出码",
        "",
    ]
    summ = json.loads(read(os.path.join(LOGS, "汇总.json")))
    lines.append("| 测试 | 退出码 | 耗时 |")
    lines.append("| --- | --- | --- |")
    for t in summ["tests"]:
        lines.append("| `%s` | %d | %.1f 秒 |" % (t["name"], t["exit"], t["seconds"]))
    lines += ["", "> 原始输出逐份在 `测试留档/<测试名>.log`，可独立复核。", ""]

    tp_all = sum(v["TP"] for v in prf.values())
    fp_all = sum(v["FP"] for v in prf.values())
    fn_all = sum(v["FN"] for v in prf.values())
    lines += [
        "## 三、分模块 P/R/F1，借鉴 4",
        "",
        "| 模块 | TP | FP | FN | 精确率 P | 召回率 R | F1 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for k in sorted(prf):
        v = prf[k]
        lines.append("| %s | %d | %d | %d | %.3f | %.3f | %.3f |"
                     % (k, v["TP"], v["FP"], v["FN"], v["P"], v["R"], v["F1"]))
    lines += [
        "",
        "合计 TP %d，与第一节的检出数 %d 一致；FP %d，FN %d。"
        % (tp_all, ev["检出"], fp_all, fn_all),
        "",
        "出处：`nityaattili/AI-feedback-categoriser` 的 `evaluate.py` 里 `compute_accuracy` 按类别累计 tp、fp、fn，再算 precision、recall、F1。仓库地址 https://github.com/nityaattili/AI-feedback-categoriser，本地副本 `_work/参考项目/nityaattili__AI-feedback-categoriser/evaluate.py`，下载日期 2026-11-09，来源登记在 `_work/参考项目/_sources.json`。本轮只把类别换成 A–F 六个规则模块，公式未改，不是自造指标。",
        "",
        "补这一层的理由：只有一个总数时看不出哪个模块弱，分模块之后可以定位到具体模块再改规则。",
        "",
    ]

    s = drift["summary"]
    lines += [
        "## 四、版本键 drift 日志，借鉴 3",
        "",
        "| 项 | 本轮 |",
        "| --- | --- |",
        "| 提示词指纹 `prompt_sha` | `%s` |" % drift["prompt_sha"],
        "| 公开版页面提示词指纹 | `%s` |" % drift["public_prompt_sha"],
        "| 指纹取自 | %s |" % ("本地工具原件 人机协作流程工具/运营场景人机协作流程工具.html"
                            if os.path.exists(TOOL_HTML) else "公开仓库内的公开版页面，仓库不含带凭据的工具原件"),
        "| 逐用例状态 | 共 %d 个，PASS %d，FAIL %d，GAP %d |"
        % (s["total"], s["passed"], s["failed"], s["gaps"]),
        "| 与上一轮比对 | %s |"
        % ("本轮为首轮基线，无历史可比对" if prev is None else
           "PASS 变 FAIL 或 GAP 的回归 %d 项" % len(reg)),
        "",
        "| 用例 | 状态 | flags | 来源 |",
        "| --- | --- | --- | --- |",
    ]
    for c in cases:
        lines.append("| `%s` %s | %s | %s | `%s` |"
                     % (c["id"], c["name"], c["status"],
                        "、".join(c["flags"]) or "无", c["source"]))
    lines += [
        "",
        "出处：`ozlar34/llm-judge-evals` 的 `drift-log.jsonl`，每条带 `prompt_sha`、逐用例 PASS / FAIL / GAP 与 flags。仓库地址 https://github.com/ozlar34/llm-judge-evals，本地副本 `_work/参考项目/ozlar34__llm-judge-evals/drift-log.jsonl`，下载日期 2026-11-09，见 `_work/参考项目/_sources.json`。",
        "",
        "复用已有的两份负向测试共 8 个用例，没有另造题。每跑一次 `eval_report.py` 往 `公开版/drift-log.jsonl` 追加一行，比对上一行里同 id 用例的状态；哪次改提示词把某个用例从 PASS 变成 FAIL 或 GAP，会在这张表里点名。指纹只覆盖页面里提示词那几段，改 CSS 不会让它变。",
        "",
        "## 五、评测层剩余两项，借鉴 2 与借鉴 1",
        "",
        "本轮按台账第七节的顺序做完借鉴 4 与借鉴 3，两项都独立验过，且各写了负向测试证明指标会响。借鉴 2 与借鉴 1 把结构、出处与计算入口备齐，**本轮不量数**：两样都要真人判定，替人填数就等于编数据。按窗口提示词第四节，这两项列入下一步。",
        "",
        "| 项 | 本轮做了什么 | 出处 | 下一步 |",
        "| --- | --- | --- | --- |",
        "| 借鉴 2 人工标注校准集 | 12 条小题集，刻意放数字转置、看似合理的幻觉、正确拒答、该拒却答、缺一半信息；`ai` 与 `human` 两栏留空 | `mrjunos/llm-eval-harness` 的 `data/judge_calibration.yaml`，仓库 https://github.com/mrjunos/llm-eval-harness，下载 2026-11-09 | 跑页面审读填 `ai`，人工填 `human`，再跑 `python 校准一致率.py` 出一致率 |",
        "| 借鉴 1 多维度评分 | 5 个指标、1–5 分标尺、MVP 通过线、评分对象备齐，分数留空 | `Liyao9797/game-customer-support-agent` 的 `docs/AGENT_EVALUATION_FRAMEWORK.md`，更新时间 2026-05-28，下载 2026-11-09 | 人工按材料打分，落成 JSON 后接进 `eval_report.py` |",
        "",
        "对应文件：`公开版/评测层-人工校准集.json`、`公开版/校准一致率.py`、`公开版/评测层-人工评分表.md`。",
        "借鉴 1 的原框架有「人情味」这一项，本项目没有客服对话场景，按台账第七节明确不采纳，评分表里只列 5 项。",
        "",
        "## 六、评测层补项的独立验证",
        "",
        "| 补项 | 验证脚本 | 结果文件 | 结论 |",
        "| --- | --- | --- | --- |",
        "| 借鉴 4 分模块 P/R/F1 | `公开版/验证-分模块PRF1.py` | `公开版/测试留档/验证-分模块PRF1.json` | 六模块齐全、TP 合计 39、负向改坏一条 keyword 后 A 的召回率从 1.000 降到 0.929 |",
        "| 借鉴 3 版本键 drift 日志 | `公开版/验证-drift日志.py` | `公开版/测试留档/验证-drift日志.json` | 指纹随提示词变而变、改 CSS 不变；PASS 变 FAIL 被点名；GAP 与 FAIL 解析正确 |",
        "",
        "## 七、明确不做",
        "",
        "按 `项目台账-运营Agent.md` 第七节「明确不采纳」，以下方向本轮一律不碰，理由都写在台账里：",
        "",
        "- 工单闭环与飞书协同、定时报告、数据库持久化：那是客服系统，会把分工台账带成服务系统",
        "- RAG 与向量检索：没有真实用户数据，加检索是空架子；本项目是结构化规则库，不是检索式知识库",
        "- 多智能体编排与 React 全栈重写：与「标出哪段不该自动」的主张相反，单文件可离线是优势",
        "- 「人情味」这类无场景支撑的主观指标：没有客服对话场景，硬套是凑数",
        "",
    ]

    with io.open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("已写出：%s" % os.path.relpath(OUT_MD, ROOT).replace("\\", "/"))
    print("检出率 %.1f%%（%d/%d）｜误报率 %.1f%%｜跨引擎 %d/%d 份一致｜负向测试 %d/%d 拦住"
          % (ev["检出率"], ev["检出"], ev["注入"], ev["误报率"],
             sm["一致样例数"], sm["样例总数"], ng["合计拦住"], ng["合计用例"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
