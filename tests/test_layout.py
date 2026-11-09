# -*- coding: utf-8 -*-
"""泳道图格式检查：一条命令跑完 11 个任务。

为什么要用 Python 走这一趟：这台机器上 node 被禁止派生任何子进程（连 cmd.exe 都 EBUSY），
而调浏览器正是要派生子进程。所以拆开——node 只负责渲染（render_flows.js），
调 Chrome 与判定交给 Python。

判定四类问题：卡片跑出泳道、文字没有完整落在卡片里、同卡片内两行文字相叠、
介入标签横向压到一起。判据全部来自浏览器里真实的文字包围盒，不靠估字数。

用法：python test_layout.py        退出码 0 表示 11 个任务全过。
"""
import html
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "_shots", "_run")
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

BROWSER_CANDS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_browser():
    for p in BROWSER_CANDS:
        if p and os.path.isfile(p):
            return p
    return None


def run_render():
    """让 node 渲染 11 个任务，输出可测量的 HTML。node 不派生进程，只读文件算 SVG。"""
    r = subprocess.run([NODE, "render_flows.js"], cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="ignore", timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        print("[失败] 渲染出错：")
        print(out[-1500:])
        sys.exit(1)
    rows = []
    for ln in (r.stdout or "").split("\n"):
        m = re.match(r"\s*task-(\d+)\t(.+?)\t(\d+) 步\t图宽 (\d+)", ln)
        if m:
            rows.append((m.group(1), m.group(2), int(m.group(3)), int(m.group(4))))
    if not rows:
        print("[失败] 没解析到任务清单：")
        print(out[-800:])
        sys.exit(1)
    return rows


def measure(browser, page):
    """在浏览器里量真实文字包围盒，取回页面写好的判定结果。"""
    url = "file:///" + page.replace("\\", "/")
    args = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--user-data-dir=" + os.path.join(RUN, "_profile"),
            "--virtual-time-budget=3000", "--window-size=1500,900", "--dump-dom", url]
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="ignore", timeout=120)
    except subprocess.TimeoutExpired:
        return "(浏览器超时)"
    out = r.stdout or ""
    m = re.search(r'<pre id="out">([\s\S]*?)</pre>', out)
    if not m:
        return "(没取到测量结果，浏览器输出 %d 字符)" % len(out)
    return html.unescape(m.group(1)).strip()


def main():
    browser = find_browser()
    if not browser:
        print("[失败] 找不到 Chrome 或 Edge，无法做真实包围盒测量")
        return 1

    rows = run_render()
    print("=== 泳道图格式检查（%d 个任务）===" % len(rows))
    print("浏览器：%s" % os.path.basename(browser))
    print()

    bad = []
    for no, name, steps, w in rows:
        page = os.path.join(RUN, "task-%s.html" % no)
        got = measure(browser, page)
        ok = got == "OK"
        if not ok:
            bad.append((no, name, got))
        print("  %s  task-%s  %s（%d 步，图的宽 %d）" % ("通过" if ok else "失败", no, name, steps, w))
        if not ok:
            print("         %s" % got)

    print()
    if bad:
        print("结果：%d / %d 通过，%d 个任务有格式问题" % (len(rows) - len(bad), len(rows), len(bad)))
        return 1
    print("结果：%d / %d 全部通过（文字不越界、不重叠，卡片都在泳道内）" % (len(rows), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
