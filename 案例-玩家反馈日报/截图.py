# -*- coding: utf-8 -*-
"""截三张工具界面图：泳道图全貌、打标结果、自检结果。

怎么做的：不另做示意图，而是把工具页面读进来另存一份副本，在副本末尾注入一小段脚本，
调用工具自己的 render() / renderTag() / runModules() / resHtml() 渲染真实数据，再用
无头浏览器截图。所以图上看到的就是工具渲染出来的，图里的表是真跑出来的那张表。

刻意不做的：不碰 运营场景人机协作流程工具.html 一个字。注入只写进副本，
副本放 _过程/截图用/，不进交付目录。

为什么用 Python 调浏览器：这台机器上 node 不能派生任何子进程，调 Chrome 必须走 Python。

用法：python 截图.py
"""
import html as htmlmod
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "人机协作流程工具", "运营场景人机协作流程工具.html")
PROC = os.path.join(HERE, "_过程")
TMP = os.path.join(PROC, "截图用")
OUT = os.path.join(HERE, "截图")
RAW = os.path.join(HERE, "01_原始反馈与来源.md")
TAGGED = os.path.join(PROC, "打标第二步-逐条打标.md")
FINAL = os.path.join(HERE, "02_玩家反馈日报-终稿.md")

BROWSER_CANDS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def read(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def find_browser():
    for p in BROWSER_CANDS:
        if p and os.path.isfile(p):
            return p
    return None


base = read(TOOL)
raw_txt = read(RAW)[:8000]
tagged_txt = read(TAGGED)
final_txt = read(FINAL)

# 三张图各自要隐藏什么、注入什么
SHOTS = [
    {
        "file": "01-泳道图全貌.png",
        "w": 1460,
        "js": """
      render('feedback_daily');
      /* 只留左栏与泳道图，把 AI 与自检那一大段收起来 */
      document.getElementById('linkbox').style.display = 'none';
      document.querySelector('.panel2').style.display = 'none';
      document.querySelector('details.ref').style.display = 'none';
      document.querySelector('footer').style.display = 'none';
"""
    },
    {
        "file": "02-打标结果.png",
        "w": 1460,
        "js": """
      render('feedback_daily');
      document.querySelector('.prob').style.display = 'none';
      document.querySelector('.flowbox').style.display = 'none';
      document.getElementById('detail').style.display = 'none';
      document.querySelector('.panel2').style.display = 'none';
      document.querySelector('details.ref').style.display = 'none';
      document.querySelector('footer').style.display = 'none';
      document.getElementById('raw').value = %s;
      document.getElementById('tag_out').innerHTML = renderTag(%s);
      (function(){
        var low = (document.getElementById('tag_out').innerHTML.match(/class="low"/g) || []).length;
        document.getElementById('tag_sum').textContent = low
          ? ('有 ' + low + ' 条标为待确认，先看这些；其余也过一眼')
          : '打完了。这次没标出待确认，全表都得过一眼';
      })();
      /* 成文与自检那两块先收起来，这一张只看打标 */
      (function(){
        var box = document.getElementById('tag_out'), n = box.nextElementSibling;
        while (n) { var nx = n.nextElementSibling; n.remove(); n = nx; }
      })();
""" % (json.dumps(raw_txt, ensure_ascii=False), json.dumps(tagged_txt, ensure_ascii=False))
    },
    {
        "file": "03-自检结果.png",
        "w": 1460,
        "js": """
      render('feedback_daily');
      document.querySelector('.prob').style.display = 'none';
      document.querySelector('.flowbox').style.display = 'none';
      document.getElementById('detail').style.display = 'none';
      document.querySelector('.panel2').style.display = 'none';
      document.querySelector('details.ref').style.display = 'none';
      document.querySelector('footer').style.display = 'none';
      document.getElementById('draft').value = %s;
      /* 跑的是页面自己的规则引擎，不是别处算好的结果 */
      (function(){
        var r = runModules(%s, 'feedback_table');
        var o = resHtml(r);
        document.getElementById('sc_result').innerHTML = o.html;
        document.getElementById('sc_sum').textContent = '待处理项合计 ' + o.total + ' 项' +
          (o.total ? '，改完重跑至归零即可交付' : '，可直接交付');
      })();
      /* 打标与成文那两块收起来，这一张只看自检 */
      (function(){
        var lk = document.getElementById('linkbox'), nodes = [].slice.call(lk.children);
        var idx = -1;
        for (var i = 0; i < nodes.length; i++) {
          if (nodes[i].tagName === 'H4' && nodes[i].textContent.indexOf('交付前自检') > -1) { idx = i; break; }
        }
        if (idx > 0) nodes.slice(0, idx).forEach(function(n){ n.remove(); });
      })();
      document.getElementById('draft').style.height = '84px';
""" % (json.dumps(final_txt, ensure_ascii=False), json.dumps(final_txt, ensure_ascii=False))
    },
]

INJECT = """
<style>*,*::before,*::after{animation:none!important;transition:none!important}</style>
<pre id="__h" style="display:none">0</pre>
<script>
(function(){
  try{
%s
  }catch(e){
    document.getElementById('__h').textContent = 'ERR ' + e.message;
    return;
  }
  /* 量内容底边，不量 scrollHeight：页面背景层比内容高，按 scrollHeight 截会留一大片空白 */
  var maxB = 0;
  [].forEach.call(document.querySelector('.wrap').children, function(c){
    if (c.getBoundingClientRect) { var b = c.getBoundingClientRect().bottom; if (b > maxB) maxB = b; }
  });
  document.getElementById('__h').textContent = String(Math.ceil(maxB));
})();
</script>
"""


def build(shot, path):
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(base + (INJECT % shot["js"]))


def run_chrome(browser, extra, url, timeout=180):
    args = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--user-data-dir=" + os.path.join(TMP, "_profile"),
            "--hide-scrollbars", "--force-device-scale-factor=1",
            "--virtual-time-budget=4000"] + extra + [url]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="ignore", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def main():
    browser = find_browser()
    if not browser:
        print("[失败] 找不到 Chrome 或 Edge")
        return 1
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    print("浏览器：%s" % browser)
    print()

    results = []
    for i, shot in enumerate(SHOTS, 1):
        page = os.path.join(TMP, "shot-%02d.html" % i)
        build(shot, page)
        url = "file:///" + page.replace("\\", "/")

        dom = run_chrome(browser, ["--dump-dom"], url)
        m = re.search(r'<pre id="__h"[^>]*>([\s\S]*?)</pre>', dom)
        val = htmlmod.unescape(m.group(1)).strip() if m else "(没取到高度)"
        if not m or not val.isdigit():
            print("[失败] %s 渲染出错：%s" % (shot["file"], val))
            results.append((shot["file"], "失败", val))
            continue
        h = int(val) + 16

        png = os.path.join(OUT, shot["file"])
        run_chrome(browser, ["--screenshot=" + png,
                             "--window-size=%d,%d" % (shot["w"], h)], url)
        ok = os.path.isfile(png) and os.path.getsize(png) > 3000
        results.append((shot["file"], "成功" if ok else "失败",
                        "%d×%d　%.1f KB" % (shot["w"], h, os.path.getsize(png) / 1024.0 if ok else 0)))
        print("  %s  %s  %s" % ("成功" if ok else "失败", shot["file"], results[-1][2]))

    print()
    bad = [r for r in results if r[1] != "成功"]
    print("结果：%d / %d 张截成" % (len(results) - len(bad), len(results)))
    print("输出目录：%s" % OUT)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
