# -*- coding: utf-8 -*-
"""分步调用验证：一次只让它做一件事。

假设：把「合并 / 过滤 / 打标」塞进一段提示词，模型会顾此失彼；
拆成两次调用，每次一个主任务，稳定性应该更好。
"""
import json, re, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HTML = os.path.join(ROOT, "运营场景人机协作流程工具.html")
MAT = os.path.join(HERE, "原始反馈-公开渠道采集.md")
OUT = os.path.join(HERE, "打标结果-第5轮-分步.md")

URL = "https://apihub.agnes-ai.com/v1/chat/completions"
MODEL = "agnes-3.0-flash"


def read_key():
    t = open(HTML, encoding="utf-8").read()
    enc = json.loads(re.search(r"var LLM_KEY_ENC = (\[[^\]]*\]);", t).group(1))
    salt = int(re.search(r"var LLM_KEY_SALT = (\d+);", t).group(1))
    s = "".join(chr(b ^ ((salt + i * 29) & 255)) for i, b in enumerate(enc))
    return s.split("\x00")[0]


def ask(prompt, temp=0):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read().decode())
    if "error" in r:
        raise RuntimeError(r["error"])
    return r["choices"][0]["message"]["content"]


KEY = read_key()

# ---- 第一步：只做合并与过滤，不要求表格、不打标 ----
P1 = ('下面是从各渠道导出的玩家原始反馈。请做两件事，做完就停。\n'
      '一、合并：说的是同一件事的多条反馈合成一条。\n'
      '二、过滤：纯发泄、说不出具体问题的剔掉。语气激烈但讲了具体问题的要留。\n'
      '输出一份清单，每行一条，格式：编号 | 摘要 | 来源渠道 | 共N条提及\n'
      '只输出这份清单，不要打标，不要加其他字段，不要写表格。\n'
      '最后另起一行，用「剔除N条：」开头说明剔了几条、为什么。\n\n【原始反馈】\n')

# ---- 第二步：拿合并后的清单打标（沿用页面里那段提示词的字段口径）----
P2 = ('你是游戏运营的反馈整理助手。下面已经合并去重过的反馈清单，请逐条打标。\n'
      '用 Markdown 表格输出，列固定为：序号 | 摘要 | 来源渠道 | 反馈类型 | 归属模块 | 影响范围 | 紧急度 | 可复现 | 置信度 | 备选归属\n'
      '字段口径：\n'
      '- 反馈类型：客户端、玩法系统、内容体验、版本、内容合规-本地化 五类里选一个\n'
      '- 归属模块：具体到功能或系统名，不要写「其他」\n'
      '- 紧急度：高／中／低。问的是运营要不要跟进；官方公告里已修复的属于已闭环，标低\n'
      '- 可复现：只对技术类缺陷填，照抄原文给的触发条件，原文没提机型就不要写机型。主观体验写「不适用」\n'
      '- 置信度：高／中／低。下列情况必须写低：① 玩家给的是方案建议不是问题描述；② 分类处在两类边界；③ 你补充了原文没有的判断。写低时在最后一列给另一种归属\n'
      '- 内容合规-本地化：多语言、本地化文案缺失或错译归这一类\n'
      '最后另起一段，用「待确认：」列出置信度为低的条目序号与理由。\n\n【反馈清单】\n')

t0 = time.time()
raw = open(MAT, encoding="utf-8").read()
step1 = ask(P1 + raw[:8000])
print("=== 第一步（合并+过滤）：%.1f 秒 ===" % (time.time() - t0))
print(step1)
print()

t1 = time.time()
step2 = ask(P2 + step1)
print("=== 第二步（打标）：%.1f 秒 ===" % (time.time() - t1))
print(step2)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("# 打标结果（第 5 轮 · 拆成两次调用）\n\n")
    f.write("> 思路：把「合并 / 过滤 / 打标」拆开，一次只让它做一件事。\n")
    f.write("> 模型：%s　温度 0\n\n---\n\n" % MODEL)
    f.write("## 第一步　合并与过滤\n\n")
    f.write(step1 + "\n\n---\n\n## 第二步　打标\n\n")
    f.write(step2)
print("\n已写出：", OUT)
