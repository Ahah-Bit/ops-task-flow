# -*- coding: utf-8 -*-
"""借鉴 2 的计算入口：填完人工判定与 AI 审读结果后，一条命令算一致率。

ai 栏填 AI 审读的判定，human 栏必须由真人填。两栏没齐时，脚本会如实打印「还差几条」
并退出，不会拿空值凑一个数，也不会替人判定。填法：把 评测层-人工校准集.json
里每条的 ai 与 human 填成 ACCEPTABLE 或 REJECTED，再跑本脚本。

出处：mrjunos/llm-eval-harness 的 data/judge_calibration.yaml，用 judge 与 human
的一致率当信任指标，并区分不对称失败。仓库地址
https://github.com/mrjunos/llm-eval-harness，下载日期 2026-11-09。

用法：python 校准一致率.py
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "评测层-人工校准集.json")
OUT = os.path.join(HERE, "测试留档", "校准一致率.json")
VALID = ("ACCEPTABLE", "REJECTED")


def main():
    data = json.loads(io.open(SRC, encoding="utf-8").read())
    cases = data["cases"]
    missing_ai = [c["id"] for c in cases if c.get("ai", "").strip() not in VALID]
    missing_human = [c["id"] for c in cases if c.get("human", "").strip() not in VALID]
    if missing_ai or missing_human:
        print("本轮不计算一致率：AI 审读待填 %d 条，人工判定待填 %d 条，共 %d 题。"
              % (len(missing_ai), len(missing_human), len(cases)))
        print("原因：human 栏必须由真人填；ai 栏是 AI 审读判定，不是替人填的数。")
        print("下一步：由李霖峰按 评测层-判定核对表.md 逐条填 human，再跑本脚本。")
        return 0

    agree = [c for c in cases if c["ai"] == c["human"]]
    asym = [c for c in cases if c["ai"] == "ACCEPTABLE" and c["human"] == "REJECTED"]
    rec = {
        "题数": len(cases), "一致条数": len(agree),
        "一致率": round(len(agree) / len(cases) * 100, 1),
        "漏放行": len(asym),
        "漏放行题号": [c["id"] for c in asym],
        "反向不一致": [c["id"] for c in cases
                    if c["ai"] == "REJECTED" and c["human"] == "ACCEPTABLE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    print("一致率 %.1f%%，%d/%d 条；漏放行 %d 条。" %
          (rec["一致率"], len(agree), len(cases), rec["漏放行"]))
    print("已写出：测试留档/校准一致率.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
