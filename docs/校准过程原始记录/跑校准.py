# -*- coding: utf-8 -*-
"""把校准材料喂进工具的打标提示词，跑一轮真实调用。

【适用轮次】第 1～4 轮用的是这个脚本，对应工具里「单次调用」那版提示词。
    第 5 轮起工具已改成两次调用（TAG_P1 / TAG_P2 两个常量），
    这个脚本读的是旧的 `var prompt =`，现在跑会找不到。**当前有效的是
    `跑校准-页面代码.py`**，它直接从 HTML 取 TAG_P1/TAG_P2 的真实值。
    保留本脚本是为了留档单次调用版的实验过程。
"""

密钥与提示词都从 运营场景人机协作流程工具.html 里现读，
保证跑的就是页面里那段，不是另抄的版本。
"""
import json, re, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 工具根目录
HTML = os.path.join(ROOT, "运营场景人机协作流程工具.html")
MAT = os.path.join(HERE, "原始反馈-公开渠道采集.md")
OUT = os.path.join(HERE, "打标结果-第1轮.md")

URL = "https://apihub.agnes-ai.com/v1/chat/completions"
MODEL = "agnes-3.0-flash"


def html_text():
    return open(HTML, encoding="utf-8").read()


def read_key(t):
    enc = json.loads(re.search(r"var LLM_KEY_ENC = (\[[^\]]*\]);", t).group(1))
    salt = int(re.search(r"var LLM_KEY_SALT = (\d+);", t).group(1))
    s = "".join(chr(b ^ ((salt + i * 29) & 255)) for i, b in enumerate(enc))
    return s.split("\x00")[0]


def read_prompt(t, fn_name, stop_name):
    """从 JS 源码里拼出某个函数里 prompt 变量的真实字符串。"""
    blk = t[t.index("function " + fn_name + "()"):t.index("function " + stop_name)]
    m = re.search(r"var prompt = ([\s\S]*?);\n", blk)
    expr = m.group(1)
    parts = re.findall(r"'((?:[^'\\]|\\.)*)'", expr)
    out = []
    for p in parts:
        out.append(p.replace("\\n", "\n").replace("\\'", "'").replace("\\\\", "\\"))
    return "".join(out)


def ask(prompt, temp):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + read_key(html_text())})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read().decode())
    if "error" in r:
        raise RuntimeError(r["error"])
    return r["choices"][0]["message"]["content"]


def main():
    rnd = sys.argv[1] if len(sys.argv) > 1 else "1"
    out_path = os.path.join(HERE, "打标结果-第%s轮.md" % rnd)

    t = html_text()
    key = read_key(t)
    print("凭据解码：%d 位，前缀 %s…" % (len(key), key[:6]))

    tpl = read_prompt(t, "runTag", "renderTag")
    print("打标提示词：%d 字，末段=%s" % (len(tpl), tpl[-40:].replace("\n", "\\n")))

    raw = open(MAT, encoding="utf-8").read()
    print("材料：%d 字" % len(raw))
    full = tpl + raw[:8000]          # 提示词末尾已经带了「【原始反馈】」标记

    t0 = time.time()
    txt = ask(full, 0)
    dt = time.time() - t0
    print("耗时 %.1f 秒，返回 %d 字" % (dt, len(txt)))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# 打标结果（第 %s 轮 · 真实调用）\n\n" % rnd)
        f.write("> 输入材料：`校准材料/原始反馈-公开渠道采集.md`（32 条）\n")
        f.write("> 提示词：直接取自 `运营场景人机协作流程工具.html` 里 `runTag()` 的实现\n")
        f.write("> 模型：%s　温度 0　耗时 %.1f 秒\n\n" % (MODEL, dt))
        f.write("---\n\n")
        f.write(txt)
    print("已写出：", out_path)
    print()
    print(txt)


if __name__ == "__main__":
    main()
