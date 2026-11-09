# -*- coding: utf-8 -*-
"""步骤 3：把散在页面数据、规则库、模板、校准材料里的条目收成一份可查清单。

每条写三样：条目内容、出处、被哪条自检规则检查。数字全部从文件里数出来，不手写。
产出：公开版/知识条目清单.json、公开版/知识条目清单.md、测试留档/知识条目核对.json

边界写死在文件开头：**这是结构化规则库，不是检索式知识库**，不往 RAG 上靠。

用法：python 生成知识条目.py
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "人机协作流程工具")
SELF = os.path.join(ROOT, "运营自检")
HTML = os.path.join(TOOL, "运营场景人机协作流程工具.html")
VERIFY = os.path.join(TOOL, "verify_flows.py")
CHECKLIST = os.path.join(SELF, "checklist.json")
TEMPLATE_DIR = os.path.join(TOOL, "模板")
CALIB_DIR = os.path.join(TOOL, "校准材料")
OUT_JSON = os.path.join(HERE, "知识条目清单.json")
OUT_MD = os.path.join(HERE, "知识条目清单.md")
OUT_CHECK = os.path.join(HERE, "测试留档", "知识条目核对.json")

BOUNDARY = "这是结构化规则库，不是检索式知识库。条目按固定字段存、按固定规则查，没有向量检索，也不按语义召回。"

MOD_FILES = {
    "A": "A_number_check.py", "B": "B_wording_check.py", "C": "C_structure_check.py",
    "D": "D_consistency_check.py", "E": "E_source_check.py", "F": "F_enum_count_check.py",
}

TEMPLATE_USE = {
    "玩家反馈日报模板.md": "玩家反馈日报的字段定义与分类口径，兼作可试跑草稿",
    "试跑记录.md": "模板试跑时登记的字段误用与口径问题",
}

CALIB_USE = {
    "原始反馈-公开渠道采集.md": "六轮校准用的公开渠道原始素材",
    "打标校准-第1轮问题清单.md": "第 1 轮暴露的 6 个问题，据此把打标拆成两次调用",
    "跑校准-页面代码.py": "从页面现取提示词跑校准的脚本",
    "全链初稿-最新.md": "全链跑出来的成文初稿",
    "全链结果-打标成文自检.md": "打标、成文、自检三段合起来的留档",
    "校准总结.md": "六轮对照的结论",
    "回归用例-成文初稿-含已知问题.md": "带已知问题的回归稿，用来验规则引擎会不会报",
    "跑全链-页面代码.py": "端到端现取页面提示词的脚本，本轮修好并加了离线取值模式",
}


def read(p):
    return io.open(p, encoding="utf-8").read()


def load_flows():
    t = read(HTML)
    m = re.search(r'<script type="application/json" id="flows">([\s\S]*?)</script>', t)
    return json.loads(m.group(1))


def add(items, cat, eid, content, source, checked, note=""):
    items.append({"类别": cat, "编号": eid, "条目内容": content,
                  "出处": source, "被哪条自检规则检查": checked, "备注": note})


def main():
    data = load_flows()
    meta, tasks = data["meta"], data["tasks"]
    cfg = json.loads(read(CHECKLIST))
    items = []

    # 1 六个规则模块
    for k, desc in meta["module_names"].items():
        add(items, "规则模块", "rule-" + k, desc,
            "人机协作流程工具/运营场景人机协作流程工具.html 的 meta.module_names.%s；实现在 运营自检/%s"
            % (k, MOD_FILES[k]),
            "它本身就是规则，由 运营自检/eval.py 的注入样例与 公开版/验证-分模块PRF1.py 的分模块 P/R/F1 检查")

    # 2 六类交付物的规则
    for key, v in cfg["deliverable_types"].items():
        content = "%s；必含栏目 %s；禁用表述 %s；空泛表述 %s" % (
            v["name"], "、".join(v["required_sections"]) or "无",
            "、".join(v["forbidden_wording"]) or "无",
            "、".join(v["soft_wording"]) or "无")
        add(items, "交付物类型规则", "type-" + key, content,
            "运营自检/checklist.json 的 deliverable_types.%s；同源副本在页面 meta.check_engine.types.%s"
            % (key, key),
            "页面 meta.selfcheck_rules.%s 指定的模块 %s；verify_flows.py 的内嵌引擎与 checklist.json 逐类比对"
            % (key, "+".join(meta["selfcheck_rules"].get(key, []))))

    # 3 岗位任务清单 12 项，从校验脚本现读
    vsrc = read(VERIFY)
    jstart = vsrc.index("JOBS = [")
    jblock = vsrc[jstart:vsrc.index("]", jstart)]
    jobs = re.findall(r'\("([^"]+)", "([^"]+)"\)', jblock)
    for i, (line, name) in enumerate(jobs, 1):
        add(items, "岗位任务清单", "job-%02d" % i, "%s · %s" % (line, name),
            "人机协作流程工具/verify_flows.py 的 JOBS；原出处 岗位任务与AI融入分析.md 第二节十二项重复性任务",
            "verify_flows.py 覆盖率校验，已覆盖的写进任务的 maps_to，未覆盖的登记在 meta.job_coverage.excluded")

    # 4 11 项任务
    for t in tasks:
        add(items, "流程任务", "task-" + t["id"],
            "%s · %s，交付物 %s，节奏 %s，对应岗位任务 %s" %
            (t["line"], t["name"], t["deliverable"], t["cadence"], t["maps_to"]),
            "人机协作流程工具/运营场景人机协作流程工具.html 的 tasks.%s" % t["id"],
            "verify_flows.py 结构完整校验，TASK_REQUIRED 的 11 个字段齐全；selfcheck 与 meta.selfcheck_rules 对接校验")

    # 5 74 步
    for t in tasks:
        for s in t["steps"]:
            add(items, "流程步骤", "%s-s%02d" % (t["id"], s["no"]),
                "第 %d 步 %s；目标 %s；自动化档位 %s；分工 %s" %
                (s["no"], s["title"], str(s["goal"])[:60], s["auto"], s["raci"]),
                "人机协作流程工具/运营场景人机协作流程工具.html 的 tasks.%s.steps[%d]" % (t["id"], s["no"] - 1),
                "verify_flows.py 六要素校验，STEP_REQUIRED 的 14 个字段齐全；另查分工依据、引用出处与覆盖率归位")

    # 6 模板
    for fn, use in TEMPLATE_USE.items():
        add(items, "模板", "tpl-" + fn, fn + "：" + use,
            "人机协作流程工具/模板/" + fn,
            "按该模板写出的成稿由 C 模块查必含栏目、E 模块查引用出处、F 模块查数量与枚举；模板本身由 verify_flows.py 的栏目比对间接校验",
            "模板是检查口径的来源，不是被检的成稿")

    # 7 校准材料
    for fn in sorted(os.listdir(CALIB_DIR)):
        p = os.path.join(CALIB_DIR, fn)
        if not os.path.isfile(p):
            continue
        use = CALIB_USE.get(fn, "校准过程留档")
        checked = ("回归用例稿由 跑自检.py 实际检过；其余是校准输入，不直接被 A 到 F 检查"
                   if not fn.endswith(".py") else
                   "由 公开版/步骤1验收.py 的离线取值链路验证")
        if fn == "跑全链-页面代码.py":
            checked = "由 公开版/步骤1验收.py 调 --只取提示词 离线验证，退出码 0"
        add(items, "校准材料", "cal-" + fn, fn + "：" + use,
            "人机协作流程工具/校准材料/" + fn, checked,
            "校准材料用于调整规则口径，不是被检对象")

    # 8 行业检查清单
    for it in meta["industry_items"]:
        add(items, "行业检查清单", "ind-" + it["id"],
            "%s，判为%s" % (it["name"], "范围内" if it["scope"] == "in" else "范围外"),
            "人机协作流程工具/运营场景人机协作流程工具.html 的 meta.industry_items.%s；清单原文 %s"
            % (it["id"], it["from"]),
            "verify_flows.py 行业检查项覆盖校验，范围内每条都要能在某个流程步骤里找到归宿，找不到即判失败")

    # 9 五准则
    for c in meta["criteria"]:
        add(items, "分工判据", "crit-" + c["key"], "%s：%s" % (c["key"], c["note"]),
            "人机协作流程工具/运营场景人机协作流程工具.html 的 meta.criteria.%s" % c["key"],
            "verify_flows.py 有依据校验，每处人机分工都要标替代档位与五准则")

    # 10 四档位
    for t in meta["tiers"]:
        add(items, "自动化档位", "tier-" + t["id"], "%s %s：%s" % (t["id"], t["name"], t["note"]),
            "人机协作流程工具/运营场景人机协作流程工具.html 的 meta.tiers.%s" % t["id"],
            "verify_flows.py 有依据校验，AUTO_BY_TIER 规定每档允许开到多高")

    # 自检：三要素齐全，计数与源文件一致
    total_steps = sum(len(t["steps"]) for t in tasks)
    counts = {}
    for i in items:
        counts[i["类别"]] = counts.get(i["类别"], 0) + 1
    checks = [
        ("每条三要素都非空", all(i["条目内容"] and i["出处"] and i["被哪条自检规则检查"] for i in items)),
        ("规则模块 6 条", counts.get("规则模块") == 6),
        ("交付物类型 6 条", counts.get("交付物类型规则") == len(cfg["deliverable_types"]) == 6),
        ("岗位任务清单 12 条", counts.get("岗位任务清单") == len(jobs) == 12),
        ("流程任务 11 条", counts.get("流程任务") == len(tasks) == 11),
        ("流程步骤 74 条", counts.get("流程步骤") == total_steps == 74),
        ("行业清单条数与页面一致", counts.get("行业检查清单") == len(meta["industry_items"])),
    ]

    doc = {"_边界": BOUNDARY,
           "_说明": "每条写条目内容、出处、被哪条自检规则检查。由 公开版/生成知识条目.py 从源文件现读生成，数字不手写。",
           "_生成时的源文件": ["人机协作流程工具/运营场景人机协作流程工具.html",
                          "运营自检/checklist.json", "人机协作流程工具/verify_flows.py",
                          "人机协作流程工具/模板/", "人机协作流程工具/校准材料/"],
           "_分类计数": counts, "_条目总数": len(items), "条目": items}
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    # Markdown：按类别分节，74 步单独一节用紧凑表
    lines = [
        "# 知识条目清单",
        "",
        "> **" + BOUNDARY + "**",
        "",
        "每条写三样：条目内容、出处、被哪条自检规则检查。由 `公开版/生成知识条目.py` 从源文件现读生成，共 %d 条。" % len(items),
        "",
        "## 分类计数",
        "",
        "| 类别 | 条数 |",
        "| --- | --- |",
    ]
    for k in sorted(counts):
        lines.append("| %s | %d |" % (k, counts[k]))
    lines += ["", "| 合计 | %d |" % len(items), ""]
    for cat in ["规则模块", "交付物类型规则", "岗位任务清单", "流程任务", "模板", "校准材料",
                "行业检查清单", "分工判据", "自动化档位"]:
        rows = [i for i in items if i["类别"] == cat]
        lines += ["## " + cat, "", "| 编号 | 条目内容 | 出处 | 被哪条自检规则检查 |",
                  "| --- | --- | --- | --- |"]
        for i in rows:
            lines.append("| `%s` | %s | %s | %s |" %
                         (i["编号"], i["条目内容"].replace("|", "／"),
                          i["出处"].replace("|", "／"), i["被哪条自检规则检查"].replace("|", "／")))
        lines.append("")
    steps = [i for i in items if i["类别"] == "流程步骤"]
    lines += ["## 流程步骤，共 %d 步" % len(steps), "",
              "| 编号 | 条目内容 | 出处 | 被哪条自检规则检查 |", "| --- | --- | --- | --- |"]
    for i in steps:
        lines.append("| `%s` | %s | %s | %s |" %
                     (i["编号"], i["条目内容"].replace("|", "／"),
                      i["出处"].replace("|", "／"), "verify_flows.py 六要素与出处校验，14 个字段齐全"))
    lines += ["", "## 边界", "", BOUNDARY,
              "", "条目按固定字段存、按固定规则查，没有向量检索，也不按语义召回。",
              "对照 `项目台账-运营Agent.md` 第七节「明确不采纳」，本项目不引入 RAG，也不把这套规则库说成检索式知识库。", ""]
    with io.open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    checks.append(("边界句写进清单 md 与 json",
                   BOUNDARY in "\n".join(lines) and doc.get("_边界") == BOUNDARY))

    rec = {"核对项": [{"项": a, "通过": b} for a, b in checks],
           "全部通过": all(b for _, b in checks),
           "分类计数": counts, "条目总数": len(items),
           "流程任务数": len(tasks), "流程步骤数": total_steps}
    os.makedirs(os.path.dirname(OUT_CHECK), exist_ok=True)
    with io.open(OUT_CHECK, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    for a, b in checks:
        print(("  [通过] " if b else "  [失败] ") + a)
    print("\n共 %d 条，已写出 知识条目清单.json 与 知识条目清单.md" % len(items))
    return 0 if rec["全部通过"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
