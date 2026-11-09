# -*- coding: utf-8 -*-
"""跑自检.py —— 把流程工具的产出直接送进自检工具，一条命令跑完。

存在的理由：自检工具读的是自己目录下的 checklist.json，每次要跑都得手改 target 和
target_type 两个字段。这一步是机械的、容易改错，正好该自动化。

做法：把自检工具复制一份到本目录的 _run/，只改副本里的那两个字段，在副本里跑。
**不改动 运营自检/ 里的任何文件。** 副本每次覆盖，不需要删目录。

用法：
    python 跑自检.py <待检文件路径> <交付物类型>
    python 跑自检.py 我的反馈日报.md feedback_table
    python 跑自检.py            # 不带参数时列出可用类型与用法

交付物类型取自 运营自检/checklist.json，与流程引导器里标注的类型键一致。
"""
import io
import json
import os
import shutil
import subprocess
import sys

SELF_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.abspath(os.path.join(SELF_DIR, "..", "运营自检"))
RUN_DIR = os.path.join(SELF_DIR, "_run")
CONFIG = os.path.join(TOOL_DIR, "checklist.json")


def load_config():
    if not os.path.exists(CONFIG):
        sys.exit("找不到自检工具的规则文件：%s" % CONFIG)
    with io.open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def show_usage(cfg):
    print("用法：python 跑自检.py <待检文件路径> <交付物类型>")
    print("")
    print("可用的交付物类型（取自 运营自检/checklist.json）：")
    for k, v in (cfg.get("deliverable_types") or {}).items():
        print("  %-18s %s" % (k, v.get("name", "")))
    print("")
    print("流程引导器里每个任务标注的自检类型，就是从这份表里取的。")


def main():
    cfg = load_config()
    types = cfg.get("deliverable_types") or {}

    if len(sys.argv) < 3:
        show_usage(cfg)
        return 0 if len(sys.argv) == 1 else 2

    target = os.path.abspath(sys.argv[1])
    dtype = sys.argv[2].strip()

    if dtype not in types:
        print("[失败] 类型「%s」不在自检工具的规则里。" % dtype)
        print("")
        show_usage(cfg)
        return 2

    if not os.path.exists(target):
        print("[失败] 待检文件不存在：%s" % target)
        return 2

    # 1 把工具复制到 _run（覆盖式，不删目录）
    os.makedirs(RUN_DIR, exist_ok=True)
    copied = 0
    for name in os.listdir(TOOL_DIR):
        src = os.path.join(TOOL_DIR, name)
        if os.path.isfile(src) and name.endswith(".py"):
            shutil.copy2(src, os.path.join(RUN_DIR, name))
            copied += 1
        elif name == "sample" and os.path.isdir(src):
            shutil.copytree(src, os.path.join(RUN_DIR, "sample"), dirs_exist_ok=True)

    # 2 只改副本里的两个字段
    run_cfg = json.loads(json.dumps(cfg))
    run_cfg["target"] = target
    run_cfg["target_type"] = dtype
    with io.open(os.path.join(RUN_DIR, "checklist.json"), "w", encoding="utf-8") as f:
        json.dump(run_cfg, f, ensure_ascii=False, indent=2)

    print("=" * 68)
    print("跑自检　类型：%s（%s）" % (dtype, types[dtype].get("name", "")))
    print("待检文件：%s" % target)
    print("副本目录：%s　（已复制 %d 个脚本，未改动 运营自检/ 本体）" % (RUN_DIR, copied))
    print("=" * 68)

    # 3 在副本里跑
    r = subprocess.run([sys.executable, os.path.join(RUN_DIR, "run_all.py")],
                       cwd=RUN_DIR, capture_output=True, text=True, encoding="utf-8")
    print(r.stdout)
    if r.returncode != 0:
        print("STDERR:\n%s" % r.stderr[-2000:])
        return r.returncode

    total = ""
    for ln in r.stdout.splitlines():
        if ln.startswith("  待处理项合计"):
            total = ln.strip()
    print("结果：%s" % (total or "见上方汇总"))
    print("逐条明细：%s" % os.path.join(RUN_DIR, "output"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
