# -*- coding: utf-8 -*-
"""步骤 1.2 第二条：修 E 模块只认弯引号、在本项目稿子上空转的问题。

本项目纪律要求引号统一用「」，而 E 模块的 QUOTE_RE 只认 “” 与 ASCII 引号，
结果是它对自己项目的稿子永远报「未发现问题」。改识别规则，并补一条用例，
证明旧规则不报、新规则会报。

同时回归 eval.py，确认 39/39 与零误报没有被这条改动带偏。
用法：python 修E模块-直角引号.py
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SELF = os.path.join(ROOT, "运营自检")
E_FILE = os.path.join(SELF, "E_source_check.py")
CASE = os.path.join(HERE, "用例-E模块直角引号.md")
OUT = os.path.join(HERE, "测试留档", "E模块核对.json")


CASE_TEXT = """# E 模块识别用例

> 用途：证明 E 模块现在能认出直角引号「」包裹的引用，同时不把版本名当引用。
> 这一行带了「来源」二字，属于已标注，不该被报。

「这次活动页面的按钮太小了，手指老是点歪，点了好几次都没反应」。

「能不能给常驻角色也加一点新东西，老角色没什么上场机会」（出处：B站动态 2026-09-21）。

4.6 版本「月升之前，与兽共舞」正式上线，新场景生研院同步开放。
"""


def find_quote_line(src):
    for line in src.splitlines():
        if line.startswith("QUOTE_RE = re.compile("):
            return line
    return None


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    src = io.open(E_FILE, encoding="utf-8").read()
    line = find_quote_line(src)
    if line is None:
        print("[失败] E_source_check.py 里找不到 QUOTE_RE 定义")
        return 1
    note = ("# 识别四类引号：弯引号 “”、ASCII 引号、直角引号「」与双直角『』。\n"
            "# 本项目统一用「」，旧规则只认前两类，导致在自己的稿子上永远查不到引用。\n")
    if "「『" in line:
        print("E 模块已带直角引号识别，跳过改写")
    else:
        newline = 'QUOTE_RE = re.compile(r"[\u201c\\"\'「『]([^\u201d\\"\'」』]{6,60})[\u201d\\"\'」』]")'
        src2 = src.replace(line, note + newline, 1)
        io.open(E_FILE, "w", encoding="utf-8", newline="").write(src2)
        print("E_source_check.py 的 QUOTE_RE 已加入「」与『』")

    if not os.path.exists(CASE):
        io.open(CASE, "w", encoding="utf-8").write(CASE_TEXT)
        print("已写出用例：公开版/用例-E模块直角引号.md")

    # 逐条验：旧规则不报，新规则会报，且报的是用例里那条缺出处的引用
    sys.path.insert(0, SELF)
    import common
    import E_source_check as E
    common.set_target(CASE)
    common.set_type("feedback_table")
    common.set_verbose(False)

    old_re = re.compile('[\u201c"\']([^\u201d"\']{6,60})[\u201d"\']')
    new_re = E.QUOTE_RE
    try:
        E.QUOTE_RE = old_re
        old_findings = E.run()
    finally:
        E.QUOTE_RE = new_re
    new_findings = E.run()

    checks = [
        ("旧规则在该用例上查不到引用", len(old_findings) == 0),
        ("新规则在该用例上报出问题", len(new_findings) >= 1),
        ("报的正是缺出处的那条", any("按钮太小" in f.get("issue", "") for f in new_findings)),
        ("带出处的那条没被误报", not any("常驻角色" in f.get("issue", "") for f in new_findings)),
        ("版本名没被当引用报出", not any("月升之前" in f.get("issue", "") for f in new_findings)),
        ("用例里只报该报的那一条", len(new_findings) == 1),
        ("专名判定口径写在配置里",
         "quote_name_before" in json.load(io.open(os.path.join(SELF, "checklist.json"), encoding="utf-8")).get("e_module_config", {})),
    ]

    # 回归：改动不能把评测集的检出率或误报数带偏
    r = subprocess.run([sys.executable, os.path.join(SELF, "eval.py")], cwd=SELF,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
    ev = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"合计：注入 (\d+) 项，检出 (\d+) 项，检出率 ([\d.]+)%", ev)
    m2 = re.search(r"漏检 (\d+) 项，疑似误报 (\d+) 项", ev)
    inj, hit = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
    extra = int(m2.group(2)) if m2 else -1
    checks += [
        ("eval.py 退出码 0", r.returncode == 0),
        ("检出率仍是 39/39", inj == 39 and hit == 39),
        ("疑似误报仍是 0", extra == 0),
    ]

    rec = {
        "用例": "公开版/用例-E模块直角引号.md",
        "旧规则报出条数": len(old_findings),
        "新规则报出条数": len(new_findings),
        "新规则首条问题": new_findings[0]["issue"] if new_findings else "",
        "eval_注入": inj, "eval_检出": hit, "eval_疑似误报": extra,
        "逐条验": [{"项": a, "通过": b} for a, b in checks],
    }
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)

    for label, ok in checks:
        print(("  [通过] " if ok else "  [失败] ") + label)
    print("核对记录：测试留档/E模块核对.json")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
