# -*- coding: utf-8 -*-
"""端到端跑一遍：打标 → 成文 → 自检。

三段提示词全部从 运营场景人机协作流程工具.html 现取，跑的是工具当前代码：
    TAG_P1 / TAG_P2        打标两步
    draftPrompt()          成文，连同 countTagged / factLineOf 一起现算
    最后把成文初稿交给 运营自检/run_all.py 走「跑自检.py」跑规则引擎

v3.32 把成文那段抽成 draftPrompt() 之后，旧写法按字符串
「var prompt = '你是游戏运营日报的起草助手」去截页面代码会直接抛异常。
现在改成让 node 求值页面主脚本、直接调页面里的函数，不再依赖字符串锚点。

运行前提：页面里要有访问凭据。公开版页面已清空凭据，本脚本在公开版仓库里
只提供 --只取提示词 这个离线模式，不联网、不调接口。

用法：
    python 跑全链-页面代码.py --只取提示词     # 离线验证取值链路，退出码 0 即修好了
    python 跑全链-页面代码.py                  # 真调用三次，写出全链结果
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # 人机协作流程工具/
BASE = os.path.dirname(ROOT)                      # 工程根目录
HTML = os.path.join(ROOT, "运营场景人机协作流程工具.html")
MAT = os.path.join(HERE, "原始反馈-公开渠道采集.md")
SELF = os.path.join(BASE, "运营自检")
OUT = os.path.join(HERE, "全链结果-打标成文自检.md")
DRAFT_PATH = os.path.join(HERE, "全链初稿-最新.md")
PY = sys.executable
URL = "https://apihub.agnes-ai.com/v1/chat/completions"
MODEL = "agnes-3.0-flash"

TMP_JS = os.path.join(HERE, "_全链取提示词.js")
TMP_TAG = os.path.join(HERE, "_全链打标结果.md")


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

JS_TMPL = r"""
const fs = require('fs');
const html = fs.readFileSync(__HTML__, 'utf8');
const jsonM = html.match(/<script type="application\/json" id="flows">([\s\S]*?)<\/script>/);
const jsM = html.match(/<script>([\s\S]*?)<\/script>/);
if (!jsonM || !jsM) { console.error('[失败] 找不到数据块或脚本块'); process.exit(1); }

const store = {};
function El() {
  const o = {
    value: '', textContent: '', innerHTML: '', className: '', dataset: {},
    style: {}, attrs: {},
    classList: { toggle() {}, add() {}, remove() {} },
    addEventListener() {}, querySelector() { return El(); }, querySelectorAll() { return []; },
    appendChild() {}, removeChild() {}, click() {}, select() {}, focus() {},
    scrollIntoView() {}, getAttribute() { return null; },
    setAttribute(k, v) { o.attrs[k] = v; }
  };
  return o;
}
global.document = {
  getElementById(id) {
    if (id === 'flows') return { textContent: jsonM[1] };
    if (!store[id]) store[id] = El();
    return store[id];
  },
  querySelectorAll() { return []; },
  createElement() { return El(); },
  body: { appendChild() {}, removeChild() {} },
  addEventListener() {},
  execCommand() { return true; }
};
global.navigator = {};
global.setTimeout = function () {};
/* 不能整个覆盖 URL：node 的文件代理内部要做 instanceof 判断，覆盖后 readFileSync 会挂 */
if (typeof global.URL !== 'function') global.URL = function () {};
global.URL.createObjectURL = function () { return ''; };
if (typeof global.Blob !== 'function') global.Blob = function () {};

let API;
try {
  const src = jsM[1].replace(/^[\s\S]*?(?=var DATA)/, '') +
    'return {TAG_P1:TAG_P1, TAG_P2:TAG_P2, countTagged:countTagged, factLineOf:factLineOf,' +
    ' draftPrompt:draftPrompt, aiSpec:aiSpec, DATA:DATA};';
  API = new Function('DATA_IN', 'var DATA = DATA_IN;' + src)(JSON.parse(jsonM[1]));
} catch (e) {
  console.error('[失败] 主脚本执行出错：' + e.message);
  process.exit(1);
}
const t = API.DATA.tasks.filter(function (x) { return ((x.selfcheck || {}).type_key) === 'feedback_table'; })[0];
if (!t) { console.error('[失败] 数据块里找不到 feedback_table 这条任务'); process.exit(1); }
const spec = API.DATA.meta.check_engine.types[t.selfcheck.type_key];
const out = {tag1: API.TAG_P1, tag2: API.TAG_P2, sections: spec.required_sections};
const tagPath = __TAGPATH__;
if (tagPath) {
  const tagged = fs.readFileSync(tagPath, 'utf8');
  const cnt = API.countTagged(tagged);
  out.fact = API.factLineOf(cnt);
  out.draft = API.draftPrompt(t, spec, out.fact, tagged);
}
console.log(JSON.stringify(out));
"""


def page_prompts(tagged=None):
    """让 node 求值页面主脚本，取回当前版本的三段提示词。"""
    tag_path = "null"
    if tagged is not None:
        io.open(TMP_TAG, "w", encoding="utf-8").write(tagged)
        tag_path = json.dumps(TMP_TAG, ensure_ascii=False)
    js = (JS_TMPL.replace("__HTML__", json.dumps(HTML, ensure_ascii=False))
                .replace("__TAGPATH__", tag_path))
    io.open(TMP_JS, "w", encoding="utf-8").write(js)
    try:
        r = subprocess.run([NODE, TMP_JS], cwd=HERE, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=180)
    finally:
        for p in (TMP_JS, TMP_TAG):
            if os.path.exists(p):
                os.remove(p)
    if r.returncode != 0:
        raise RuntimeError("取页面提示词失败：\n" + (r.stdout or "") + (r.stderr or ""))
    return json.loads(r.stdout)


def ask(prompt, key, temp=0):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read().decode())
    if "error" in r:
        raise RuntimeError(r["error"])
    return r["choices"][0]["message"]["content"]


def main():
    p = page_prompts()
    print("取到提示词：打标一 %d 字、打标二 %d 字" % (len(p["tag1"]), len(p["tag2"])))
    print("成文必含栏目：%s" % "、".join(p["sections"]))

    # 离线模式：连成文那段也求值一遍，证明 draftPrompt 这条链是通的
    if "--只取提示词" in sys.argv:
        demo = ("| 序号 | 摘要 | 来源渠道 | 反馈类型 | 归属模块 | 影响范围 | 紧急度 | 可复现 | 置信度 | 备选归属 |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| 1 | 结算界面卡顿 | 工单 | 客户端 | 战斗结算 | 全服 | 高 | 必现 | 高 | - |\n")
        d = page_prompts(demo)
        print("系统统计那一行：%s" % d.get("fact", ""))
        print("成文提示词 %d 字" % len(d.get("draft", "")))
        ok = (len(p["tag1"]) > 0 and len(p["tag2"]) > 0 and len(d.get("draft", "")) > 0)
        print("离线取值链路：%s" % ("通过" if ok else "未通过"))
        return 0 if ok else 1

    t = io.open(HTML, encoding="utf-8").read()
    enc = json.loads(re.search(r"var LLM_KEY_ENC = (\[[^\]]*\]);", t).group(1))
    salt = int(re.search(r"var LLM_KEY_SALT = (\d+);", t).group(1))
    key = "".join(chr(b ^ ((salt + i * 29) & 255)) for i, b in enumerate(enc)).split("\x00")[0]
    if not key:
        print("[停止] 页面里没有访问凭据。公开版页面只支持 --只取提示词 离线验证。")
        return 2

    raw = io.open(MAT, encoding="utf-8").read()
    times = {}
    t0 = time.time(); tag1 = ask(p["tag1"] + raw[:8000], key); times["打标第一步"] = time.time() - t0
    t0 = time.time(); tag2 = ask(p["tag2"] + tag1, key);      times["打标第二步"] = time.time() - t0

    built = page_prompts(tag2)
    print("成文提示词 %d 字；系统统计那一行：%s" % (len(built["draft"]), built["fact"]))
    t0 = time.time(); draft = ask(built["draft"], key, 0.2); times["成文"] = time.time() - t0

    print("耗时：" + "　".join("%s %.1f 秒" % (k, v) for k, v in times.items()))
    print("===== 成文初稿 =====\n" + draft)

    io.open(DRAFT_PATH, "w", encoding="utf-8").write(draft)
    # 必须走 跑自检.py，直接调 run_all.py 传 target 是无效的
    r = subprocess.run([PY, os.path.join(ROOT, "跑自检.py"), DRAFT_PATH, "feedback_table"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
    sc = (r.stdout or "") + (r.stderr or "")
    print("===== 规则引擎自检 =====\n" + sc[-1200:])

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("# 端到端结果：打标 → 成文 → 自检\n\n")
        f.write("> 三段提示词全部取自 `运营场景人机协作流程工具.html` 的当前代码。\n")
        f.write("> 输入：`校准材料/原始反馈-公开渠道采集.md`\n")
        f.write("> 模型 %s　温度：打标 0、成文 0.2\n\n" % MODEL)
        f.write("## 耗时\n\n| 环节 | 秒 |\n| --- | --- |\n")
        for k, v in times.items():
            f.write("| %s | %.1f |\n" % (k, v))
        f.write("\n---\n\n## 第一步　合并与过滤\n\n" + tag1)
        f.write("\n\n---\n\n## 第二步　打标\n\n" + tag2)
        f.write("\n\n---\n\n## 第三步　成文初稿\n\n" + draft)
        f.write("\n\n---\n\n## 第四步　规则引擎自检\n\n```\n" + sc + "\n```\n")
    print("\n已写出：", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
