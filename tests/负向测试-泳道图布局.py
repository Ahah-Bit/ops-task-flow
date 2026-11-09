# -*- coding: utf-8 -*-
"""负向测试：证明 test_layout.py 真的会拦住格式问题，不是恒过。

破坏点用正则按语义定位，不写死具体数值——以后改列宽、卡片高、行距都不会失效。

两道保险，都是踩过坑才加的：
  1. 启动时若发现上次留下的备份文件，先还原。曾经因为脚本崩在还原之前，
     把破坏态的文件留了下来，下一轮读到的「原始文件」本身是坏的，结论全错。
  2. try/finally 包住破坏与验证，任何异常都先还原再往外抛。
"""
import io
import os
import re
import hashlib
import subprocess

# 这个脚本放在 工程文件留底/ 下，实际要改和要跑的是上一层的工具目录
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(HERE, "运营场景人机协作流程工具.html")
BAK = HTML + ".negtest.bak"
PY = r"C:\Users\16073\.workbuddy\binaries\python\versions\3.13.12\python.exe"

# ---------- 1 自愈：上次崩溃留下的备份先还原 ----------
if os.path.exists(BAK):
    saved = io.open(BAK, encoding="utf-8").read()
    io.open(HTML, "w", encoding="utf-8").write(saved)
    os.remove(BAK)
    print("（发现上次中断留下的备份，已先还原页面）")

orig = io.open(HTML, encoding="utf-8").read()
h0 = hashlib.md5(orig.encode("utf-8")).hexdigest()[:12]

# ---------- 2 前置校验：文件必须是正常状态才动手 ----------
MUST_HAVE = "Math.floor((bw - 20) / 13)"
if MUST_HAVE not in orig:
    print("!! 页面里的「每行字号」不是按宽度算的，可能停在上一次破坏后的状态。")
    print("   先改回 var per = Math.max(4, Math.floor((bw - 20) / 13)); 再跑。")
    raise SystemExit(1)

RE_PER = re.compile(r"(var per = )[^;]+(;)")
RE_BH = re.compile(r"(var bw = COLW - 22, bh = )(\d+)(;)")
# 标题那两行（12.5px、加粗）的 y；代码里第 1 个是第一行、第 2 个是第二行
RE_TITLE_Y = re.compile(
    r"(s\.push\('<text x=\"' \+ \(bx \+ 10\) \+ '\" y=\"' \+ \(by \+ )(\d+)"
    r"(\) \+ '\" font-size=\"12\.5\" font-weight=\"600\")")


def patch_1(t, regex, repl):
    return regex.sub(repl, t, count=1)


def patch_nth(t, regex, nth, delta):
    seen = [0]

    def rep(m):
        seen[0] += 1
        if seen[0] == nth:
            return m.group(1) + str(int(m.group(2)) + delta) + m.group(3)
        return m.group(0)
    return regex.sub(rep, t)


def patch_bh(t, value):
    return RE_BH.sub(lambda m: m.group(1) + str(value) + m.group(3), t, count=1)


def run_layout():
    r = subprocess.run([PY, "test_layout.py"], cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="ignore", timeout=900)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


n_title = len(RE_TITLE_Y.findall(orig))
print("=== 负向测试：泳道图格式检查 ===")
print("（当前文件：列宽行 %d 处、标题行 %d 处）" % (len(RE_PER.findall(orig)), n_title))
if len(RE_PER.findall(orig)) != 1 or n_title < 2:
    print("!! 定位不到要破坏的位置，脚本需要跟着改")
    raise SystemExit(1)

CASES = [
    ("每行字数写死 20，长标题一行放下必撑破卡片",
     lambda s: patch_1(s, RE_PER, lambda m: m.group(1) + "20" + m.group(2)),
     "没有完整落在卡片内"),
    ("标题第二行上移，压到第一行",
     lambda s: patch_nth(s, RE_TITLE_Y, 2, -11),
     "相叠"),
    ("标题第一行下移，压到第二行",
     lambda s: patch_nth(s, RE_TITLE_Y, 1, 13),
     "相叠"),
    ("卡片高度改小，第二行掉出卡片底",
     lambda s: patch_bh(s, 60),
     "没有完整落在卡片内"),
]

ok = 0
io.open(BAK, "w", encoding="utf-8").write(orig)   # 动手前留备份，崩了下次自愈
try:
    for name, mutate, want in CASES:
        broken = mutate(orig)
        if broken == orig:
            print("  !! 破坏没生效：%s" % name)
            continue
        io.open(HTML, "w", encoding="utf-8").write(broken)
        out, code = run_layout()
        hit = (want in out) and code != 0
        ok += 1 if hit else 0
        print("  %s %s" % ("拦住 " if hit else "没拦住", name))
        detail = [ln.strip() for ln in out.split("\n")
                  if ("失败" in ln or "文字" in ln or "相叠" in ln or "卡片" in ln or "标签" in ln)]
        for d in detail[:2]:
            print("       " + d[:92])
        if not detail:
            print("       （没有报错，退出码 %d）" % code)
        io.open(HTML, "w", encoding="utf-8").write(orig)
finally:
    io.open(HTML, "w", encoding="utf-8").write(orig)
    if os.path.exists(BAK):
        os.remove(BAK)

out, code = run_layout()
h1 = hashlib.md5(io.open(HTML, encoding="utf-8").read().encode("utf-8")).hexdigest()[:12]
last = [ln for ln in out.split("\n") if ln.startswith("结果")]
print()
print("结果：拦住 %d/%d　｜　还原后内容一致：%s　｜　还原后：%s（退出码 %d）"
      % (ok, len(CASES), "是" if h0 == h1 else "否", last[0] if last else "?", code))
