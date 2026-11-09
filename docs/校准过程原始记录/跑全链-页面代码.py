# -*- coding: utf-8 -*-
"""端到端跑一遍：打标 → 成文 → 自检。

三段提示词全部从 运营场景人机协作流程工具.html 现取，跑的是工具当前的代码：
    TAG_P1 / TAG_P2        打标两步
    runDraft 里的 prompt   成文
    最后把成文初稿交给 运营自检/run_all.py 跑规则引擎
"""
import json, re, os, subprocess, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # 人机协作流程工具/
BASE = os.path.dirname(ROOT)                      # 工程根目录
HTML = os.path.join(ROOT, "运营场景人机协作流程工具.html")
MAT = os.path.join(HERE, "原始反馈-公开渠道采集.md")
SELF = os.path.join(BASE, "运营自检")
OUT = os.path.join(HERE, "全链结果-打标成文自检.md")
NODE = r"C:\Users\16073\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"
PY = r"C:\Users\16073\.workbuddy\binaries\python\versions\3.13.12\python.exe"
URL = "https://apihub.agnes-ai.com/v1/chat/completions"
MODEL = "agnes-3.0-flash"

t = open(HTML, encoding="utf-8").read()

# 凭据
enc = json.loads(re.search(r"var LLM_KEY_ENC = (\[[^\]]*\]);", t).group(1))
salt = int(re.search(r"var LLM_KEY_SALT = (\d+);", t).group(1))
KEY = "".join(chr(b ^ ((salt + i * 29) & 255)) for i, b in enumerate(enc)).split("\x00")[0]

# 打标两段提示词：node 求值
seg_tag = t[t.index("var TAG_P1 = "):t.index("function runTag(){")]
tp1, tp2 = json.loads(subprocess.run([NODE, "-e", seg_tag + "\nconsole.log(JSON.stringify([TAG_P1,TAG_P2]));"],
                                     capture_output=True, text=True, encoding="utf-8").stdout)

# 成文提示词：模板里带 spec.required_sections 与 countTagged 的统计结果，
# 所以要把「打标结果」也一起交给 node 求值，跑出来的才是页面里真正会发出去的那段。
flows = json.loads(re.search(r'<script[^>]*id="flows"[^>]*>([\s\S]*?)</script>', t).group(1))
secs = flows["meta"]["check_engine"]["types"]["feedback_table"]["required_sections"]
seg_cnt = t[t.index("function countTagged(md){"):t.index("function runDraft(){")]
seg_draft = t[t.index("var prompt = '你是游戏运营日报的起草助手"):]
seg_draft = seg_draft[:seg_draft.index("tagged.slice(0, 8000);") + len("tagged.slice(0, 8000);")]
seg_draft = seg_draft.replace("tagged.slice(0, 8000)", "tagged.slice(0, 8000)", 1)


def build_draft_prompt(tag2):
    js = (seg_cnt + "\n" +
          "var spec = {required_sections: %s};\n" % json.dumps(secs, ensure_ascii=False) +
          "var tagged = %s;\n" % json.dumps(tag2, ensure_ascii=False) +
          "var cnt = countTagged(tagged); var fact = factLineOf(cnt);\n" +
          seg_draft.replace("var prompt =", "var tpl =", 1) + "\n" +
          "console.log(JSON.stringify({tpl: tpl, fact: fact}));")
    out = subprocess.run([NODE, "-e", js], capture_output=True, text=True, encoding="utf-8")
    return json.loads(out.stdout)

print("取到提示词：打标一 %d 字、打标二 %d 字" % (len(tp1), len(tp2)))
print("成文必含栏目：%s" % "、".join(secs))
print()


def ask(prompt, temp=0):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read().decode())
    if "error" in r:
        raise RuntimeError(r["error"])
    return r["choices"][0]["message"]["content"]


raw = open(MAT, encoding="utf-8").read()
times = {}

t0 = time.time(); tag1 = ask(tp1 + raw[:8000]); times["打标第一步"] = time.time() - t0
t0 = time.time(); tag2 = ask(tp2 + tag1);        times["打标第二步"] = time.time() - t0

built = build_draft_prompt(tag2)
print("成文提示词 %d 字；系统统计那一行：%s" % (len(built["tpl"]), built["fact"]))
print()
t0 = time.time(); draft = ask(built["tpl"]); times["成文"] = time.time() - t0

print("耗时：" + "　".join("%s %.1f 秒" % (k, v) for k, v in times.items()))
print()
print("===== 成文初稿 =====")
print(draft)
print()

# 交给规则引擎。
# 注意：必须走 跑自检.py，不能直接调 run_all.py ——
# run_all.py 是用 subprocess 逐模块跑的，checklist.json 里的 target 传不到子进程，
# 直接调它只会一直检它自己目录下那个默认样例，传参是无效的。
draft_path = os.path.join(HERE, "全链初稿-最新.md")
open(draft_path, "w", encoding="utf-8").write(draft)
r = subprocess.run([PY, os.path.join(ROOT, "跑自检.py"), draft_path, "feedback_table"],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
sc = (r.stdout or "") + (r.stderr or "")
print("===== 规则引擎自检 =====")
print(sc[-1200:])

with open(OUT, "w", encoding="utf-8") as f:
    f.write("# 端到端结果：打标 → 成文 → 自检\n\n")
    f.write("> 三段提示词全部取自 `运营场景人机协作流程工具.html`，跑的是工具当前代码。\n")
    f.write("> 输入：`校准材料/原始反馈-公开渠道采集.md`（32 条真实公开素材）\n")
    f.write("> 模型 %s　温度：打标 0、成文 0.2（与页面一致）\n\n" % MODEL)
    f.write("## 耗时\n\n| 环节 | 秒 |\n| --- | --- |\n")
    for k, v in times.items():
        f.write("| %s | %.1f |\n" % (k, v))
    f.write("\n---\n\n## 第一步　合并与过滤\n\n" + tag1)
    f.write("\n\n---\n\n## 第二步　打标\n\n" + tag2)
    f.write("\n\n---\n\n## 第三步　成文初稿\n\n" + draft)
    f.write("\n\n---\n\n## 第四步　规则引擎自检\n\n```\n" + sc + "\n```\n")
print("\n已写出：", OUT)
