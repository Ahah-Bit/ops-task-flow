# -*- coding: utf-8 -*-
"""步骤 1.4 留档：跑两份负向测试，原始输出逐份存 log。

负向测试会临时破坏工具页面再自动还原，跑完务必核对页面 md5 是否回到
f630f63f70b6a99c98723bf0262c4730。核对动作在 步骤1验收.py 里单独做。

用法：python 跑负向测试.py
"""
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "人机协作流程工具")
KEEP = os.path.join(TOOL, "工程文件留底")
OUT = os.path.join(HERE, "测试留档")
PY = sys.executable

TESTS = [
    ("负向测试-v332.py", os.path.join(KEEP, "负向测试-v332.py"), TOOL, 600),
    ("负向测试-泳道图布局.py", os.path.join(KEEP, "负向测试-泳道图布局.py"), TOOL, 900),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    summary = []
    for name, script, cwd, timeout in TESTS:
        t0 = time.time()
        try:
            r = subprocess.run([PY, script], cwd=cwd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
            out, err, code = r.stdout or "", r.stderr or "", r.returncode
        except subprocess.TimeoutExpired as e:
            out, err, code = (e.stdout or ""), "超时 %d 秒" % timeout, 124
        text = out + (("\n[stderr]\n" + err) if err.strip() else "")
        with io.open(os.path.join(OUT, name + ".log"), "w", encoding="utf-8") as f:
            f.write(text)
        dur = time.time() - t0
        summary.append({"name": name, "exit": code, "seconds": round(dur, 1),
                        "log": "测试留档/" + name + ".log"})
        print("%-28s 退出码 %-4s %6.1f 秒" % (name, code, dur))
        for line in text.splitlines():
            if ("结果" in line or "已还原" in line or "负向测试结果" in line):
                print("   " + line.strip()[:160])
    with io.open(os.path.join(OUT, "负向测试汇总.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
