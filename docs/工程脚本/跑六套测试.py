# -*- coding: utf-8 -*-
"""步骤 1 留档：一条命令跑完六套测试，逐套把原始输出存成 log。

为什么要留原始输出：eval_report.py 的四个数必须从实际输出里读出来，不能写死。
每套测试的 stdout / stderr 都原样落在 测试留档/ 下，可独立复核。

用法：python 跑六套测试.py
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
SELF = os.path.join(ROOT, "运营自检")
OUT = os.path.join(HERE, "测试留档")
PY = sys.executable


def find_node():
    """本机 node 的版本目录会变，提示词里记的 22.22.2-3 已不存在。按目录名探测。"""
    base = r"C:\Users\16073\.workbuddy\binaries\node\versions"
    if os.path.isdir(base):
        for d in sorted(os.listdir(base), reverse=True):
            p = os.path.join(base, d, "node.exe")
            if os.path.isfile(p):
                return p
    return "node"


NODE = find_node()

TESTS = [
    ("smoke_test.js", [NODE, "smoke_test.js"], TOOL, 180),
    ("test_edge.js", [NODE, "test_edge.js"], TOOL, 180),
    ("test_layout.py", [PY, "test_layout.py"], TOOL, 300),
    ("test_live.js", [NODE, "test_live.js"], TOOL, 420),
    ("verify_flows.py", [PY, "verify_flows.py"], TOOL, 180),
    ("eval.py", [PY, os.path.join(SELF, "eval.py")], SELF, 180),
]

# 真调用那套依赖外部接口，偶发 503 / 队列满。只重试一次，首次日志原样留档，
# 不把失败抹掉。其余五套是纯本地确定性测试，不重试。
RETRY_ON = {
    "test_live.js": ["ServiceUnavailableError", "The request queue is full", "503", "接口调用失败"],
}


def main():
    os.makedirs(OUT, exist_ok=True)
    summary = {"node": NODE, "python": PY, "tests": []}
    for name, cmd, cwd, timeout in TESTS:
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
            out, err, code = r.stdout or "", r.stderr or "", r.returncode
        except subprocess.TimeoutExpired as e:
            out, err, code = (e.stdout or ""), "超时 %d 秒" % timeout, 124
        attempts, first_exit = 1, None
        if code != 0 and name in RETRY_ON and any(k in (out + err) for k in RETRY_ON[name]):
            with io.open(os.path.join(OUT, name + ".attempt1.log"), "w", encoding="utf-8") as f:
                f.write(out + (("\n[stderr]\n" + err) if err.strip() else ""))
            first_exit, attempts = code, 2
            print("  %s 首次遇到外部服务故障，保留 attempt1.log 并重跑一次" % name)
            try:
                r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=timeout)
                out, err, code = r.stdout or "", r.stderr or "", r.returncode
            except subprocess.TimeoutExpired as e:
                out, err, code = (e.stdout or ""), "超时 %d 秒" % timeout, 124

        text = out + (("\n[stderr]\n" + err) if err.strip() else "")
        with io.open(os.path.join(OUT, name + ".log"), "w", encoding="utf-8") as f:
            f.write(text)
        dur = time.time() - t0
        item = {"name": name, "exit": code, "seconds": round(dur, 1),
                "stdout_bytes": len(out), "log": "测试留档/" + name + ".log",
                "attempts": attempts, "first_exit": first_exit}
        summary["tests"].append(item)
        print("%-20s 退出码 %-4s %6.1f 秒　%s" % (name, code, dur, item["log"]))

    with io.open(os.path.join(OUT, "汇总.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    bad = [t["name"] for t in summary["tests"] if t["exit"] != 0]
    print("\n全部通过" if not bad else "\n未通过：" + "、".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
