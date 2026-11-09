# -*- coding: utf-8 -*-
"""步骤 1.2 第一条：统一「可复现」栏的填写口径。

冲突：页面打标提示词要写「不适用」，玩家反馈日报模板要写「—」。
以模板为准，把口径落到两个机器可读的地方：
  1. 公开版页面的打标提示词 TAG_P2
  2. 运营自检/checklist.json 里 feedback_table 的规则说明
模板文件本身已是「—」口径，作为基准保留不动。

只改公开版页面，原页面一个字节不动。
用法：python 修口径-可复现.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PUB = os.path.join(HERE, "运营场景人机协作流程工具.html")
ORIG = os.path.join(ROOT, "人机协作流程工具", "运营场景人机协作流程工具.html")
TEMPLATE = os.path.join(ROOT, "人机协作流程工具", "模板", "玩家反馈日报模板.md")
CHECKLIST = os.path.join(ROOT, "运营自检", "checklist.json")

OLD = "剧情、手感、平衡感受这类主观体验一律写「不适用」"
NEW = "剧情、手感、平衡感受这类主观体验一律写「—」，不要写「不适用」，与玩家反馈日报模板同一口径"
NOTE_ADD = "；「可复现」栏只对缺陷写发生规律，非缺陷类填「—」，不写「不适用」，与玩家反馈日报模板同一口径"


def main():
    html = io.open(PUB, encoding="utf-8").read()
    if OLD in html:
        html = html.replace(OLD, NEW, 1)
        io.open(PUB, "w", encoding="utf-8", newline="").write(html)
        print("公开版 TAG_P2 已改为「—」口径")
    elif NEW in html:
        print("公开版 TAG_P2 已是「—」口径，跳过")
    else:
        print("[失败] 公开版里找不到打标提示词的那句话")
        return 1

    cfg = json.load(io.open(CHECKLIST, encoding="utf-8"))
    notes = cfg["deliverable_types"]["feedback_table"]["notes"]
    if "非缺陷类填「—」" not in notes:
        cfg["deliverable_types"]["feedback_table"]["notes"] = notes + NOTE_ADD
        with io.open(CHECKLIST, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("checklist.json 的 feedback_table 已补口径说明")
    else:
        print("checklist.json 已带口径说明，跳过")

    # 逐条验：三处口径一致，且公开版不再要求写「不适用」
    html2 = io.open(PUB, encoding="utf-8").read()
    tpl = io.open(TEMPLATE, encoding="utf-8").read()
    cfg2 = json.load(io.open(CHECKLIST, encoding="utf-8"))
    notes2 = cfg2["deliverable_types"]["feedback_table"]["notes"]
    checks = [
        ("公开版提示词写「—」", NEW in html2),
        ("公开版不再要求写「不适用」", OLD not in html2),
        ("模板是「—」口径", "非缺陷条目写「—」" in tpl),
        ("规则库与模板同口径", "非缺陷类填「—」" in notes2),
        ("原页面未被改动", OLD in io.open(ORIG, encoding="utf-8").read()),
    ]
    for label, ok in checks:
        print(("  [通过] " if ok else "  [失败] ") + label)
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
