# -*- coding: utf-8 -*-
"""负向测试：人为破坏四处，看两套测试是否报出「对应」的失败项。

只跑一次通过，证明不了测试有效——它可能只是不响。做法是破坏 → 看是否报对 → 自动还原。
"""
import io
import os
import re
import shutil
import subprocess
import hashlib

# 这个脚本放在 工程文件留底/ 下，实际要改和要跑的是上一层的工具目录
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(HERE, "运营场景人机协作流程工具.html")
BAK = HTML + ".negtest.bak"


def find_node():
    """本机 node 版本目录会变，按目录名探测，不写死版本号。"""
    base = r"C:\Users\16073\.workbuddy\binaries\node\versions"
    if os.path.isdir(base):
        for d in sorted(os.listdir(base), reverse=True):
            p = os.path.join(base, d, "node.exe")
            if os.path.isfile(p):
                return p
    return "node"


NODE = find_node()

CASES = [
    ("把 report 类错分到核稿型", "if (k === 'report') {", "if (k === '永不匹配的键') {",
     "test_edge.js", "分派错了"),
    ("去掉等待动画的进度条结构", "'<div class=\"ldbar\"><i></i></div></div>';", "'';",
     "smoke_test.js", "等待提示没有动画结构"),
    ("停下时不复位运行状态", "  JOB.on = false;\n  jobBar();\n  toast('已停下", "  jobBar();\n  toast('已停下",
     "test_edge.js", "停下之后 JOB.on"),
    ("错误提示丢掉指定区域参数", "stepFail('AI 审读', '初稿框是空的', 'llm_out')", "stepFail('AI 审读', '初稿框是空的')",
     "test_edge.js", "空初稿的提示"),
]

# 自愈：上次中断留下的备份先还原，避免把破坏态当成原始文件
if os.path.exists(BAK):
    saved = io.open(BAK, encoding="utf-8").read()
    io.open(HTML, "w", encoding="utf-8").write(saved)
    os.remove(BAK)
    print("（发现上次中断留下的备份，已先还原页面）")

orig = io.open(HTML, encoding="utf-8").read()
# 前置校验：页面必须是正常状态才动手
if "if (k === 'report') {" not in orig:
    print("!! 页面不是正常状态，先还原再跑")
    raise SystemExit(1)

ORIG_MD5 = hashlib.md5(open(HTML, "rb").read()).hexdigest()
shutil.copy2(HTML, BAK)
print("已备份。原始 %d 字符，md5 %s" % (len(orig), ORIG_MD5))
print()

caught = 0
try:
    for i, (title, a, b, runner, want) in enumerate(CASES, 1):
        if orig.count(a) != 1:
            print("用例 %d：锚点出现 %d 次，跳过 —— %s" % (i, orig.count(a), title))
            continue
        io.open(HTML, "w", encoding="utf-8").write(orig.replace(a, b, 1))
        r = subprocess.run([NODE, os.path.join(HERE, runner)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="ignore", cwd=HERE, timeout=120)
        out = (r.stdout or "") + (r.stderr or "")
        fails = [l.strip() for l in out.split("\n") if l.strip().startswith("- ")]
        hit = any(want in f for f in fails)
        print("用例 %d：%s" % (i, title))
        print("   跑 %s，退出码 %d，报出 %d 项" % (runner, r.returncode, len(fails)))
        for f in fails[:3]:
            print("     " + f)
        if r.returncode != 0 and hit:
            print("   -> 拦住，且报的是对应项")
            caught += 1
        elif r.returncode != 0:
            print("   -> 报了错但没报对应项，期望包含：%s" % want)
        else:
            print("   -> !! 没拦住")
        print()
finally:
    io.open(HTML, "w", encoding="utf-8").write(orig)
    same = io.open(HTML, encoding="utf-8").read() == orig
    r2 = subprocess.run([NODE, os.path.join(HERE, "smoke_test.js")],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="ignore", cwd=HERE, timeout=120)
    r3 = subprocess.run([NODE, os.path.join(HERE, "test_edge.js")],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="ignore", cwd=HERE, timeout=120)
    if os.path.exists(BAK):
        os.remove(BAK)
    md5_now = hashlib.md5(open(HTML, "rb").read()).hexdigest()
    print("已还原：内容一致 %s｜md5 与动手前一致 %s｜冒烟退出码 %d｜边界退出码 %d（都应为 0）"
          % (same, md5_now == ORIG_MD5, r2.returncode, r3.returncode))

print()
print("负向测试结果：%d / %d 组被拦住" % (caught, len(CASES)))
