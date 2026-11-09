# -*- coding: utf-8 -*-
"""
verify_flows.py —— 「人机协作流程引导器」的完整性校验

不校验内容好不好，只校验该有的东西在不在。防的是本项目已经踩过三次的那类毛病：
枚举不全导致静默失效（某个步骤漏了「出错怎么办」、某处分工没写依据，看的时候看不出来）。

校验五件事：
 1. 结构完整  每个任务、每个步骤的必填字段是否齐全
 2. 六要素    每一步是否都有：AI 做什么（含需要的信息）/ 人做什么（含要拍的板）/ 交接点 / 产出物 / 出错怎么办
 3. 有依据    每处人机分工是否都标了替代档位与五准则
 4. 有出处    每处引用是否都能追到来源
 5. 覆盖率    本工具覆盖了岗位任务清单里的几项，缺哪些；没画的必须登记理由，账要平

用法：
    python verify_flows.py

退出码 0 表示全部通过，1 表示存在失败项。
"""
import json
import re
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "运营场景人机协作流程工具.html")
# 自检工具的规则文件（对接校验用）
CHECKLIST = os.path.join(HERE, "..", "运营自检", "checklist.json")
BRIEF_MAX = 40  # 首屏短句长度上限（字），超了就会把页面堆满

# 岗位任务清单（出处：根目录 岗位任务与AI融入分析.md 第二节「十二项重复性任务」）
JOBS = [
    ("产品运营线", "玩家反馈收集与清洗"),
    ("产品运营线", "版本上线配置与文案核对"),
    ("产品运营线", "版本卖点提炼"),
    ("产品运营线", "报告生成"),
    ("产品运营线", "内容效果预判"),
    ("活动运营线", "竞品与往期活动统计"),
    ("活动运营线", "活动上线前检查"),
    ("活动运营线", "活动期间数据监控"),
    ("活动运营线", "活动奖励发放与核对"),
    ("活动运营线", "活动效果分析与淘汰决策"),
    ("活动运营线", "活动方案设计"),
    ("活动运营线", "福利规划与付费点设计"),
]

TASK_REQUIRED = ["id", "name", "line", "maps_to", "deliverable", "cadence",
                 "current", "bottleneck", "sources", "triggers", "steps"]
STEP_REQUIRED = ["no", "title", "goal", "ai", "human", "handoff",
                 "handoff_note", "output", "on_error", "basis", "source", "covers", "raci", "auto"]
LANES = ("机器", "人")
AUTO_ENUM = ("全自动", "例外制", "人复核", "人决策")
# 替代档位决定自动化档位能开到多高：档一才允许全自动，档四只能是人的判断
AUTO_BY_TIER = {
    "档一": ("全自动", "例外制"),
    "档二": ("全自动", "例外制", "人复核"),
    "档三": ("人复核", "人决策"),
    "档四": ("人决策",),
}
EXC_WORDS = ("仅", "例外", "异常", "只")
HANDOFF_ENUM = ["人→AI", "AI→人", "人→AI→人"]
TIER_ENUM = ["档一", "档二", "档三", "档四"]

ok, bad, warn = [], [], []


def load_flows():
    with open(HTML, "r", encoding="utf-8") as f:
        html = f.read()
    m = re.search(
        r'<script\s+type="application/json"\s+id="flows">(.*?)</script>',
        html, re.S)
    if not m:
        print("[失败] 在 HTML 里找不到 <script type=\"application/json\" id=\"flows\"> 数据块")
        sys.exit(1)
    return json.loads(m.group(1)), html


def main():
    data, html = load_flows()

    if "meta" not in data or "tasks" not in data:
        bad.append("数据块缺少 meta 或 tasks")
    criteria_keys = [c["key"] for c in data.get("meta", {}).get("criteria", [])]
    if not criteria_keys:
        bad.append("meta.criteria 为空：五准则没写进去")

    tasks = data.get("tasks", [])
    if not tasks:
        bad.append("tasks 为空")

    covered = set()
    step_total = 0
    handoff_count = 0
    tier_dist = {}

    print("=" * 66)
    print("人机协作流程引导器 · 完整性校验")
    print("=" * 66)
    print("五准则：%s" % "、".join(criteria_keys))
    print("任务类型：%d 个" % len(tasks))
    print("")

    seen_ids = set()
    for t in tasks:
        tid = t.get("id", "?")
        print("-" * 66)
        print("【%s】%s（%s）" % (tid, t.get("name", "?"), t.get("line", "?")))

        for f in TASK_REQUIRED:
            if f not in t:
                bad.append("%s 缺字段 %s" % (tid, f))
        if tid in seen_ids:
            bad.append("%s 的 id 重复" % tid)
        seen_ids.add(tid)
        if t.get("line") not in ("产品运营线", "活动运营线"):
            bad.append("%s 的 line 取值非法：%s" % (tid, t.get("line")))

        # 覆盖率登记
        if t.get("maps_to") in [j[1] for j in JOBS]:
            covered.add(t["maps_to"])
        else:
            bad.append("%s 的 maps_to「%s」不在岗位任务清单内" % (tid, t.get("maps_to")))
        if not t.get("sources"):
            warn.append("%s 没写流程出处" % tid)
        if not t.get("triggers"):
            warn.append("%s 没写例外分支提示" % tid)

        steps = t.get("steps", [])
        print("  步骤数：%d" % len(steps))
        if not steps:
            bad.append("%s 没有步骤" % tid)

        for s in steps:
            sno = s.get("no", "?")
            tag = "%s#%d" % (tid, sno)
            step_total += 1
            for f in STEP_REQUIRED:
                if f not in s:
                    bad.append("%s 缺字段 %s" % (tag, f))

            # 2 六要素
            ai = s.get("ai", {})
            hm = s.get("human", {})
            if not ai.get("action"):
                bad.append("%s 没写 AI 做什么" % tag)
            if not ai.get("needs"):
                bad.append("%s 没写 AI 需要什么信息" % tag)
            if not hm.get("action"):
                bad.append("%s 没写人做什么" % tag)
            if not hm.get("decides"):
                bad.append("%s 没写人要拍什么板" % tag)
            if not s.get("output"):
                bad.append("%s 没写产出物" % tag)
            if not s.get("on_error"):
                bad.append("%s 没写「出错怎么办」" % tag)
            else:
                for i, e in enumerate(s["on_error"]):
                    if not e.get("if") or not e.get("then"):
                        bad.append("%s 第 %d 条出错处置不完整" % (tag, i + 1))

            # 2b 首屏短句层：没有它页面就会堆满长句
            for who, obj in (("AI", ai), ("人", hm)):
                br = obj.get("brief")
                if not br:
                    bad.append("%s 缺%s的首屏短句 brief" % (tag, who))
                elif len(br) > BRIEF_MAX:
                    bad.append("%s %s 的 brief 超长：%d 字（上限 %d）" % (tag, who, len(br), BRIEF_MAX))

            # 2c RACI：分工的标准记法。A 必须是人（行业硬规则）；R 与泳道、档位三者一致
            ra = s.get("raci", {})
            for f in ("R", "A", "C", "I", "other"):
                if not ra.get(f):
                    bad.append("%s 的 RACI 缺字段 %s" % (tag, f))
            if ra.get("A") != "人":
                bad.append("%s 的 A 不是人：%s（硬规则：A 必须是人）" % (tag, ra.get("A")))
            if ra.get("R") not in LANES:
                bad.append("%s 的 R 取值非法：%s" % (tag, ra.get("R")))
            else:
                tier = s.get("basis", {}).get("tier", "")
                want_lane = "机器" if tier in ("档一", "档二") else "人"
                if ra["R"] != want_lane:
                    bad.append("%s 的 R（%s）与替代档位 %s 不一致，应为 %s"
                               % (tag, ra["R"], tier, want_lane))
                other = ra.get("other")
                if other and other == ra["R"]:
                    bad.append("%s 的另一侧泳道标签与 R 同侧，画不出跨泳道箭头" % tag)
                if ra.get("C") and other and ra["C"] != (("人" if ra["R"] == "机器" else "机器")):
                    bad.append("%s 的 C（%s）与另一侧泳道（%s）不一致" % (tag, ra["C"], other))

            # 2d 自动化档位：能全自动的不许留给人；档位与替代程度必须一致
            au = s.get("auto")
            if au not in AUTO_ENUM:
                bad.append("%s 的自动化档位缺失或非法：%s" % (tag, au))
            else:
                tier = s.get("basis", {}).get("tier", "")
                allowed = AUTO_BY_TIER.get(tier, ())
                if au not in allowed:
                    bad.append("%s 的自动化档位「%s」与替代档位 %s 不匹配（允许：%s）"
                               % (tag, au, tier, "／".join(allowed)))
                if au in ("全自动", "例外制"):
                    ha = hm.get("action", "")
                    if not any(w in ha for w in EXC_WORDS):
                        bad.append("%s 标了「%s」，但人的动作没写成例外处理（看不出常规路径不占人）"
                                   % (tag, au))

            # 3 交接点
            hd = s.get("handoff", "")
            if hd not in HANDOFF_ENUM:
                bad.append("%s 交接点取值非法：%s" % (tag, hd))
            else:
                handoff_count += 1

            # 4 判定依据
            b = s.get("basis", {})
            if b.get("tier") not in TIER_ENUM:
                bad.append("%s 替代档位缺失或非法：%s" % (tag, b.get("tier")))
            else:
                tier_dist[b["tier"]] = tier_dist.get(b["tier"], 0) + 1
            cs = b.get("criteria", [])
            if not cs:
                bad.append("%s 没写用哪几条准则判定" % tag)
            for c in cs:
                if c not in criteria_keys:
                    bad.append("%s 引用了不在五准则里的项：%s" % (tag, c))
            if not b.get("why"):
                bad.append("%s 没写为什么这么分" % tag)

            # 5 出处
            if not s.get("source"):
                bad.append("%s 没写出处" % tag)

            flags = []
            if ai.get("action"): flags.append("AI")
            if hm.get("action"): flags.append("人")
            print("    第 %d 步 %-14s 交接:%-9s %s" % (
                sno, s.get("title", "?"), hd, "/".join(flags)))

    # 覆盖率账要平：画了的 + 登记不画的 = 岗位清单全部
    jc = data.get("meta", {}).get("job_coverage", {})
    all_jobs = [j[1] for j in JOBS]
    ex_names = []
    if not isinstance(jc, dict) or "excluded" not in jc:
        bad.append("meta 缺 job_coverage：没画的岗位任务要登记并写明理由")
    else:
        if jc.get("total") != len(JOBS):
            bad.append("job_coverage.total 写的是 %s，岗位清单是 %d 项"
                       % (jc.get("total"), len(JOBS)))
        for e in jc.get("excluded", []):
            nm = e.get("task", "?")
            for f in ("line", "task", "judgment", "reason", "why_not_drawn", "from"):
                if not e.get(f):
                    bad.append("job_coverage 里「%s」缺字段 %s" % (nm, f))
            if e.get("line") not in ("产品运营线", "活动运营线"):
                bad.append("job_coverage 里「%s」的 line 非法：%s" % (nm, e.get("line")))
            if nm not in all_jobs:
                bad.append("job_coverage 里「%s」不在岗位清单内" % nm)
            ex_names.append(nm)
        for nm in all_jobs:
            if nm not in covered and nm not in ex_names:
                bad.append("岗位任务「%s」既没画也没登记不画的理由，悬挂" % nm)
            if nm in covered and nm in ex_names:
                bad.append("岗位任务「%s」既画了又登记为不画，重复认领" % nm)

    # 覆盖率
    print("")
    print("=" * 66)
    print("覆盖率")
    print("=" * 66)
    for line, name in JOBS:
        mark = "已覆盖" if name in covered else "未覆盖"
        print("  [%s] %s　%s" % (mark, line, name))
    print("  → 覆盖 %d / %d 项岗位任务；另 %d 项登记为不画（理由已写明）"
          % (len(covered), len(JOBS), len(ex_names)))

    # 行业检查项覆盖：真实检查项有没有在流程里找到归宿
    print("")
    print("=" * 66)
    print("行业检查项覆盖（真实清单 → 流程步骤）")
    print("=" * 66)
    items = data.get("meta", {}).get("industry_items", [])
    if not items:
        bad.append("meta.industry_items 为空：没有把真实行业检查项登记进来")
    index = {}
    for it in items:
        index[it.get("id")] = it
    claimed = {}
    for t in tasks:
        for s in t["steps"]:
            for cid in s.get("covers", []):
                if cid not in index:
                    bad.append("%s#%d 宣称吸收了不存在的检查项 %s" % (t["id"], s["no"], cid))
                else:
                    claimed.setdefault(cid, []).append("%s#%d" % (t["id"], s["no"]))

    orphans = []
    for it in items:
        if it.get("scope") == "in":
            if it["id"] not in claimed:
                orphans.append(it)
        elif it.get("scope") == "out":
            if not it.get("why"):
                bad.append("判为范围外的检查项 %s 没写理由" % it["id"])
        else:
            bad.append("检查项 %s 的 scope 取值非法：%s" % (it["id"], it.get("scope")))

    ins = [i for i in items if i.get("scope") == "in"]
    outs = [i for i in items if i.get("scope") == "out"]
    print("  范围内检查项 %d 条，已归位 %d 条；判为范围外 %d 条" % (len(ins), len(ins) - len(orphans), len(outs)))
    for it in ins:
        home = "、".join(claimed.get(it["id"], [])) or "—— 无归宿"
        print("  [%s] %-3s %s" % ("已归位" if it["id"] not in [o["id"] for o in orphans] else "无归宿",
                                 it["id"], it["name"][:34]))
        print("          归宿：%s　｜　出处：%s" % (home, it.get("from", "")))
    for it in outs:
        print("  [范围外] %-3s %s　（%s）" % (it["id"], it["name"][:30], it.get("why", "")))
    if orphans:
        bad.append("有 %d 条真实行业检查项在流程里找不到归宿：%s"
                   % (len(orphans), "、".join(o["id"] for o in orphans)))

    # 与自检工具的对接校验：流程里写的类型、栏目、模块，必须在自检工具里真实存在
    print("")
    print("=" * 66)
    print("自检工具对接校验")
    print("=" * 66)
    if not os.path.exists(CHECKLIST):
        bad.append("找不到自检工具的规则文件：%s" % os.path.normpath(CHECKLIST))
    else:
        with open(CHECKLIST, "r", encoding="utf-8") as f:
            ck = json.load(f)
        dts = ck.get("deliverable_types", {})
        print("  自检工具里的交付物类型：%s" % "、".join(dts.keys()))
        # 页面内嵌引擎的规则必须与自检工具同源，否则两边会算出不同的数
        eng = data.get("meta", {}).get("check_engine", {})
        if not eng:
            bad.append("meta.check_engine 为空：页面里没有嵌入自检规则")
        else:
            if eng.get("global_rules") != ck.get("global_rules"):
                bad.append("页面内嵌的 global_rules 与 运营自检/checklist.json 不一致")
            ets = eng.get("types", {})
            for k, v in dts.items():
                e = ets.get(k)
                if e is None:
                    bad.append("页面内嵌规则缺交付物类型 %s" % k)
                    continue
                if e.get("name") != v.get("name", ""):
                    bad.append("类型 %s 的名称不一致" % k)
                for f in ("required_sections", "forbidden_wording", "soft_wording"):
                    if (e.get(f) or []) != (v.get(f) or []):
                        bad.append("类型 %s 的 %s 与自检工具不一致：页面 %s / 工具 %s"
                                   % (k, f, e.get(f), v.get(f)))
            for k in ets:
                if k not in dts:
                    bad.append("页面内嵌规则多出自检工具没有的类型 %s" % k)
            print("  内嵌引擎规则与 checklist.json 逐类比对：%d 类%s"
                  % (len(ets), "，全部一致" if not any("内嵌" in b for b in bad) else ""))
        rules = data.get("meta", {}).get("selfcheck_rules", {})
        if not rules:
            bad.append("meta.selfcheck_rules 为空：模块对照表没登记")
        for t in tasks:
            sc = t.get("selfcheck")
            tag = t["id"]
            if not sc:
                bad.append("%s 没写 selfcheck：与自检工具的对接关系缺失" % tag)
                continue
            tk = sc.get("type_key")
            if tk not in dts:
                bad.append("%s 的 type_key「%s」在自检工具里不存在" % (tag, tk))
                continue
            real = (dts[tk].get("required_sections") or [])
            mine = (sc.get("checkpoints") or [])
            if real != mine:
                bad.append("%s 的栏目与自检工具不一致：工具里是 %s，流程里写的是 %s" % (tag, real, mine))
            # 模块对照：B 只在有禁用词或软性词规则时才适用
            want = ["A"]
            if dts[tk].get("forbidden_wording") or dts[tk].get("soft_wording"):
                want.append("B")
            want += ["C", "D", "E", "F"]
            got = rules.get(tk, [])
            if got != want:
                bad.append("%s 的模块对照与自检工具不一致：应为 %s，流程里写的是 %s" % (tag, want, got))
            print("  [%s] %s（%s）→ 类型 %s｜模块 %s｜栏目 %d 项"
                  % ("一致" if real == mine and got == want else "不一致",
                     t["name"], t["line"], tk, "+".join(got), len(mine)))
            ex = sc.get("extra")
            if ex:
                ek = ex.get("type_key")
                if ek not in dts:
                    bad.append("%s 的 extra.type_key「%s」在自检工具里不存在" % (tag, ek))
                else:
                    if (dts[ek].get("required_sections") or []) != (ex.get("checkpoints") or []):
                        bad.append("%s 的 extra 栏目与自检工具不一致" % tag)
                    print("   └ 另跑一次 %s（%s）栏目 %d 项，与自检工具一致"
                          % (ek, ex.get("type_name"), len(ex.get("checkpoints") or [])))

    # 首屏文字量：按实际版式算默认要读多少字，防止又把页面堆满
    # 版式 v3：流程图只画步骤名/档位/交接标注，细节只显示当前选中的那一步
    print("")
    print("=" * 66)
    print("首屏文字量（按当前版式：图 ＋ 数字 ＋ 抽屉的四行，长句全折叠）")
    print("=" * 66)
    FIXED = 90  # 标题、图例、按钮、自检块按钮等固定标签
    for t in tasks:
        steps = t["steps"]

        def compact(s):
            return (len(s.get("ai", {}).get("brief", "")) + len(s.get("human", {}).get("brief", ""))
                    + len(s.get("handoff", "")) + len(s.get("output", "")) + len(s.get("auto", "")))

        def full(s):
            return (compact(s) + len(s.get("goal", "")) + len(s.get("handoff_note", ""))
                    + sum(len(i) for i in s.get("ai", {}).get("needs", []))
                    + sum(len(i) for i in s.get("human", {}).get("decides", []))
                    + sum(len(e.get("if", "")) + len(e.get("then", "")) for e in s.get("on_error", []))
                    + len(s.get("basis", {}).get("why", "")) + sum(len(i) for i in s.get("source", []))
                    + len(t.get("current", "")) + len(t.get("bottleneck", "")))

        flow = sum(len(s.get("title", "")) + len(s.get("basis", {}).get("tier", "")) for s in steps)
        flow += sum(len(s.get("handoff", "")) for s in steps[1:])
        top = len(t.get("maps_to", "")) + len(t.get("deliverable", "")) + len(t.get("cadence", ""))
        first = FIXED + flow + top + compact(steps[0])
        more = full(steps[0]) - compact(steps[0])
        hidden = sum(full(s) for s in steps) - compact(steps[0])
        print("  %-14s 首屏约 %4d 字　｜　点「更多」另加 %4d 字；全部展开另加 %5d 字（%d 步）"
              % (t["name"], first, more, hidden, len(steps)))
        if first > 600:
            warn.append("%s 首屏字数偏多（%d 字），建议再压" % (t["name"], first))

    print("")
    print("=" * 66)
    print("统计")
    print("=" * 66)
    print("  步骤总数：%d；交接点：%d" % (step_total, handoff_count))
    for tier in TIER_ENUM:
        print("  %s：%d 步" % (tier, tier_dist.get(tier, 0)))
    lane_m = sum(1 for t in tasks for s in t["steps"] if s.get("raci", {}).get("R") == "机器")
    print("  R＝机器：%d 步（机器泳道）；R＝人：%d 步（人泳道）" % (lane_m, step_total - lane_m))
    au_cnt = {}
    for t in tasks:
        for s in t["steps"]:
            au_cnt[s.get("auto")] = au_cnt.get(s.get("auto"), 0) + 1
    for k in AUTO_ENUM:
        print("  自动化档位 %s：%d 步" % (k, au_cnt.get(k, 0)))
    no_person = au_cnt.get("全自动", 0) + au_cnt.get("例外制", 0)
    print("  常规路径不占人：%d 步；仍需人参与：%d 步" % (no_person, step_total - no_person))

    print("")
    print("=" * 66)
    if bad:
        print("校验未通过，共 %d 项失败：" % len(bad))
        for x in bad:
            print("  [失败] %s" % x)
    else:
        print("校验通过：结构、六要素、交接点、判定依据、出处全部齐全。")
    if warn:
        print("")
        print("提示（不阻断）：%d 项" % len(warn))
        for x in warn:
            print("  [提示] %s" % x)
    print("=" * 66)

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
