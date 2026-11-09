# -*- coding: utf-8 -*-
"""借鉴 4 的独立验证：既证明它算得对，也证明它会响。

正向：六模块齐全、TP 合计等于 golden_truth 的注入项数、P/R/F1 与公式重算一致。
负向：把 golden_truth 的一份内存副本里 A 模块某条 keyword 改坏，
      看 A 的 TP 下降、FN 上升、FP 上升、R 下降。全程不改磁盘上的任何文件。

用法：python 验证-分模块PRF1.py
"""
import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval_report as R

OUT = os.path.join(HERE, "测试留档", "验证-分模块PRF1.json")


def main():
    truth = json.loads(R.read(os.path.join(R.SELF, "golden_truth.json")))
    total = sum(len(s["injected"]) for s in truth["samples"])
    rows = R.per_module_prf()
    checks = []

    def ck(label, ok, detail=""):
        checks.append({"项": label, "通过": bool(ok), "实测": detail})

    ck("六个模块都有行", sorted(rows) == list("ABCDEF"), "、".join(sorted(rows)))
    ck("TP 合计等于注入项数", sum(v["TP"] for v in rows.values()) == total,
       "%d / %d" % (sum(v["TP"] for v in rows.values()), total))
    ck("FP 合计为 0", sum(v["FP"] for v in rows.values()) == 0, str(sum(v["FP"] for v in rows.values())))
    ck("FN 合计为 0", sum(v["FN"] for v in rows.values()) == 0, str(sum(v["FN"] for v in rows.values())))

    for k, v in rows.items():
        tp, fp, fn = v["TP"], v["FP"], v["FN"]
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        ok = (abs(v["P"] - round(p, 3)) < 1e-9 and
              abs(v["R"] - round(r, 3)) < 1e-9 and
              abs(v["F1"] - round(f1, 3)) < 1e-9)
        ck("模块 %s 的 P/R/F1 与公式重算一致" % k, ok,
           "P %.3f R %.3f F1 %.3f" % (v["P"], v["R"], v["F1"]))

    # 负向：只改内存副本，不动磁盘
    broken = copy.deepcopy(truth)
    target = None
    for s in broken["samples"]:
        for item in s["injected"]:
            if item["module"] == "A":
                item["keyword"] = "这个关键词在样例里根本不存在"
                target = item
                break
        if target:
            break
    bad = R.per_module_prf(truth=broken)
    a0, a1 = rows["A"], bad["A"]
    ck("负向：改坏一条 keyword 后 A 的 TP 下降", a1["TP"] < a0["TP"],
       "%d → %d" % (a0["TP"], a1["TP"]))
    ck("负向：A 的 FN 上升", a1["FN"] > a0["FN"], "%d → %d" % (a0["FN"], a1["FN"]))
    ck("负向：A 的 FP 上升", a1["FP"] > a0["FP"], "%d → %d" % (a0["FP"], a1["FP"]))
    ck("负向：A 的召回率下降", a1["R"] < a0["R"], "%.3f → %.3f" % (a0["R"], a1["R"]))
    ck("负向：其他模块不受影响", all(bad[k] == rows[k] for k in "BCDEF"), "B–F 未变")

    rec = {"验证项": checks, "全部通过": all(c["通过"] for c in checks),
           "分模块结果": rows, "负向破坏后A模块": a1}
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    for c in checks:
        print(("  [通过] " if c["通过"] else "  [失败] ") + c["项"] +
              ("　" + str(c["实测"]) if c["实测"] else ""))
    print("\n借鉴 4 验证：" + ("全部通过" if rec["全部通过"] else "有未通过项"))
    return 0 if rec["全部通过"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
