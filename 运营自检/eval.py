# -*- coding: utf-8 -*-
"""评测：用注入法测检出率与误报率。

做法：golden/ 下的样例事先注入了已知问题，清单登记在 golden_truth.json。
本脚本逐份跑检查，比对哪些注入问题被检出、哪些漏了、哪些报出但没登记（疑似误报）。

运行：python eval.py
报告：output/99_评测报告.txt
"""
import os
import io
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import set_target, set_type, set_verbose, SELF_DIR, write_text
import A_number_check
import B_wording_check
import C_structure_check
import D_consistency_check
import E_source_check
import F_enum_count_check

MODULES = [
    ("A", A_number_check),
    ("B", B_wording_check),
    ("C", C_structure_check),
    ("D", D_consistency_check),
    ("E", E_source_check),
    ("F", F_enum_count_check),
]


def load_truth():
    with io.open(os.path.join(SELF_DIR, "golden_truth.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    set_verbose(False)
    truth = load_truth()

    out = []
    total_inj = total_hit = 0
    all_missed = []
    all_extra = []

    for s in truth["samples"]:
        path = os.path.join(SELF_DIR, s["file"])
        set_target(path)
        set_type(s["type"])

        found = {}
        for key, mod in MODULES:
            found[key] = mod.run()

        hits, missed = [], []
        for item in s["injected"]:
            key, kw = item["module"], item["keyword"]
            blob = " ".join(f.get("text", "") + f.get("issue", "") for f in found[key])
            (hits if kw in blob else missed).append(item)

        registered = {}
        for i in s["injected"]:
            registered.setdefault(i["module"], []).append(i["keyword"])

        extras = []
        for key, items in found.items():
            kws = registered.get(key, [])
            for f in items:
                blob = f.get("text", "") + f.get("issue", "")
                if not any(kw in blob for kw in kws):
                    extras.append({
                        "module": key,
                        "text": f.get("text", "")[:60],
                        "issue": f.get("issue", "")[:60],
                    })

        total_inj += len(s["injected"])
        total_hit += len(hits)
        all_missed += [dict(m, sample=s["name"]) for m in missed]
        all_extra += [dict(e, sample=s["name"]) for e in extras]

        out.append("【%s】%s" % (s["name"], s["file"]))
        out.append("  注入 %d 项，检出 %d 项，漏检 %d 项，疑似误报 %d 项" % (
            len(s["injected"]), len(hits), len(missed), len(extras)))
        for m in missed:
            out.append("    [漏检] %s 模块：%s" % (m["module"], m["desc"]))
        for e in extras[:5]:
            out.append("    [多余] %s 模块：%s" % (e["module"], e["text"]))
        out.append("")

    rate = (total_hit / total_inj * 100) if total_inj else 0.0
    out.append("=" * 62)
    out.append("合计：注入 %d 项，检出 %d 项，检出率 %.1f%%" % (total_inj, total_hit, rate))
    out.append("漏检 %d 项，疑似误报 %d 项" % (len(all_missed), len(all_extra)))
    out.append("验收线：检出率 >= 90%%，误报率 <= 10%%")
    verdict = "通过" if rate >= 90 else "未达标"
    out.append("结论：%s" % verdict)
    out.append("")
    out.append("说明：注入式评测集只验证规则自身的检出能力，不代表真实业务稿上的表现。")
    out.append("      真实公开材料的校准另做了六轮，见 校准材料/校准总结.md 与 案例-玩家反馈日报/。")

    text = "\n".join(out)
    print(text)
    write_text("99_评测报告.txt", text + "\n")


if __name__ == "__main__":
    main()
