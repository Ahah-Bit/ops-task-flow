# -*- coding: utf-8 -*-
"""一键运行五项检查，汇总输出到 output/。

运行：
    python run_all.py

只读待检文件，不修改任何内容。每个子脚本独立运行，各自报告写入 output/；
本脚本额外生成 00_汇总.txt。

待检文件与检查规则都写在 checklist.json 里，改规则不用改代码。
"""
import os
import sys
import subprocess
import datetime

SELF_DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

MODULES = [
    "A_number_check.py",
    "B_wording_check.py",
    "C_structure_check.py",
    "D_consistency_check.py",
    "E_source_check.py",
    "F_enum_count_check.py",
]


def main():
    print("=" * 68)
    print("运营交付物自检 run_all — %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 68)

    summary = []
    total = 0
    for mod in MODULES:
        path = os.path.join(SELF_DIR, mod)
        print("\n>>> 运行 %s" % mod)
        try:
            r = subprocess.run([PY, path], cwd=SELF_DIR,
                               capture_output=True, text=True, encoding="utf-8")
            if r.returncode != 0:
                summary.append("[失败] %s  返回码 %s" % (mod, r.returncode))
                print(r.stdout[-2000:])
                print("STDERR:\n", r.stderr[-2000:])
            else:
                out = r.stdout.strip()
                tail = out.splitlines()[-1] if out else ""
                n = 0
                for ln in out.splitlines():
                    if ln.startswith("合计 "):
                        try:
                            n = int(ln.replace("合计 ", "").replace(" 项", ""))
                        except ValueError:
                            n = 0
                total += n
                summary.append("[完成] %-24s %s" % (mod, tail))
                print(tail)
        except Exception as e:
            summary.append("[异常] %s : %s" % (mod, e))
            print("异常：", e)

    print("\n" + "=" * 68)
    print("汇总")
    for s in summary:
        print("  " + s)
    print("  ----")
    print("  待处理项合计：%d 项" % total)
    print("=" * 68)

    outdir = os.path.join(SELF_DIR, "output")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "00_汇总.txt"), "w", encoding="utf-8") as f:
        f.write("运营交付物自检 汇总  %s\n\n" % datetime.datetime.now())
        for s in summary:
            f.write(s + "\n")
        f.write("\n待处理项合计：%d 项\n" % total)


if __name__ == "__main__":
    main()
