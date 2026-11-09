# -*- coding: utf-8 -*-
"""借鉴 3 的独立验证：日志格式、指纹、以及「改动会被报出来」。

正向：jsonl 每行可解析、必含 prompt_sha、8 个用例状态合法、指纹与当前页面一致。
负向：
  1 改一个提示词字，指纹必须变，否则版本键形同虚设
  2 构造上一轮全 PASS、本轮一个 FAIL，对比函数必须点名这条回归
  3 构造含「跳过」与「没拦住」的模拟 log，状态解析必须给出 GAP 与 FAIL
全程不改磁盘上的任何文件。

用法：python 验证-drift日志.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval_report as R

OUT = os.path.join(HERE, "测试留档", "验证-drift日志.json")


def main():
    checks = []

    def ck(label, ok, detail=""):
        checks.append({"项": label, "通过": bool(ok), "实测": detail})

    rows = [json.loads(l) for l in R.read(R.DRIFT_LOG).splitlines() if l.strip()]
    ck("drift-log.jsonl 至少一行且每行可解析", len(rows) >= 1, "%d 行" % len(rows))
    last = rows[-1]
    ck("记录带 prompt_sha", bool(last.get("prompt_sha")), last.get("prompt_sha", ""))
    ck("记录带 public_prompt_sha", bool(last.get("public_prompt_sha")), last.get("public_prompt_sha", ""))
    cases = last.get("cases", [])
    ck("逐用例共 8 条", len(cases) == 8, str(len(cases)))
    ck("状态都在 PASS / FAIL / GAP 内",
       all(c["status"] in ("PASS", "FAIL", "GAP") for c in cases),
       "、".join(sorted(set(c["status"] for c in cases))))
    ck("每条带 id 与来源", all(c.get("id") and c.get("source") for c in cases), "8/8")
    ck("本轮指纹与工具页面一致", last["prompt_sha"] == R.prompt_fingerprint(),
       "%s / %s" % (last["prompt_sha"], R.prompt_fingerprint()))
    ck("本轮公开版指纹与公开页面一致",
       last["public_prompt_sha"] == R.prompt_fingerprint(R.read(R.PUB_HTML)),
       "%s / %s" % (last["public_prompt_sha"], R.prompt_fingerprint(R.read(R.PUB_HTML))))

    # 负向 1：提示词变了，指纹必须变
    # 公开仓库里只有公开版页面，没有带凭据的工具原件
    page = R.TOOL_HTML if os.path.exists(R.TOOL_HTML) else R.PUB_HTML
    html = R.read(page)
    changed = html.replace("var TAG_P1 = ", "var TAG_P1 = 改一个字 ")
    ck("负向：提示词改动后指纹变化", R.prompt_fingerprint(changed) != R.prompt_fingerprint(html),
       "%s → %s" % (R.prompt_fingerprint(html), R.prompt_fingerprint(changed)))
    ck("负向：只改 CSS 区域指纹不变",
       R.prompt_fingerprint(html.replace(".layout{", ".layout2{")) == R.prompt_fingerprint(html),
       "指纹未变")

    # 负向 2：PASS → FAIL 必须被点名
    prev = {"cases": [{"id": "v332-1", "status": "PASS"}, {"id": "v332-2", "status": "PASS"}]}
    curr = {"cases": [{"id": "v332-1", "status": "PASS", "name": "甲"},
                      {"id": "v332-2", "status": "FAIL", "name": "乙"}]}
    reg = R.compare_drift(prev, curr)
    ck("负向：PASS 变 FAIL 被点名", len(reg) == 1 and reg[0]["id"] == "v332-2", str(reg))
    ck("负向：无改动时不误报回归", R.compare_drift(prev, prev) == [], "空")

    # 负向 3：模拟 log 里的跳过与没拦住要解析成 GAP 与 FAIL
    fake_a = ("用例 1：锚点出现 0 次，跳过 —— 模拟\n"
              "用例 2：模拟没拦住\n   -> !! 没拦住\n"
              "用例 3：模拟拦住\n   -> 拦住，且报的是对应项\n")
    fake_b = "  拦住  模拟通过\n  没拦住  模拟失败\n"
    parsed = R.drift_cases(a=fake_a, b=fake_b)
    got = {c["id"]: c["status"] for c in parsed}
    ck("负向：锚点跳过解析为 GAP", got.get("v332-1") == "GAP", str(got.get("v332-1")))
    ck("负向：没拦住解析为 FAIL", got.get("v332-2") == "FAIL", str(got.get("v332-2")))
    ck("负向：泳道图没拦住解析为 FAIL", got.get("layout-2") == "FAIL", str(got.get("layout-2")))
    ck("负向：泳道图拦住解析为 PASS", got.get("layout-1") == "PASS", str(got.get("layout-1")))

    rec = {"验证项": checks, "全部通过": all(c["通过"] for c in checks),
           "本轮用例状态": {c["id"]: c["status"] for c in cases}}
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    for c in checks:
        print(("  [通过] " if c["通过"] else "  [失败] ") + c["项"] +
              ("　" + str(c["实测"]) if c["实测"] else ""))
    print("\n借鉴 3 验证：" + ("全部通过" if rec["全部通过"] else "有未通过项"))
    return 0 if rec["全部通过"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
