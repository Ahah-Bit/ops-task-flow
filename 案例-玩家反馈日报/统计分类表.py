# -*- coding: utf-8 -*-
"""从日报终稿里数出分类表的口径数字。

为什么单独跑这一步：条数、分类分布、可复现分布、缺陷与建议的拆分、
海外渠道参与占比，这几组数要写进「本期概况」和「分类说明」，写错一处
整份稿子的可信度就没了。数数这件事交给代码，不交给模型，也不靠手算。

用法：python 统计分类表.py [日报文件]
"""
import io
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "02_玩家反馈日报-终稿.md")

OVERSEAS = ("PTT", "巴哈姆特", "Gurugamer", "GamingSport", "Reddit", "Discord", "X", "Twitter")


def read_rows(path):
    """只认分类表：表头里必须同时有「来源渠道」与「可复现」。

    稿子里不止一张表，紧急项与处置那张表也有「编号」列。按表头认表，
    免得两张表的行混在一起数。
    """
    with io.open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    head, rows = None, []
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            if head is not None:          # 表已读完，后面的内容不再看
                break
            continue
        if re.match(r"^\|[\s:|-]+\|$", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if head is None:
            if "来源渠道" in cells and "可复现" in cells:
                head = cells
            continue
        rows.append(cells)
    return head, rows


head, rows = read_rows(DOC)
if not head or not rows:
    sys.exit("[失败] 没在 %s 里找到分类表" % DOC)

idx = {k: i for i, k in enumerate(head)}
need = ("编号", "来源渠道", "分类", "可复现", "影响范围")
miss = [k for k in need if k not in idx]
if miss:
    sys.exit("[失败] 分类表缺列：%s（现有列：%s）" % ("、".join(miss), "、".join(head)))

total = len(rows)
cls = Counter(r[idx["分类"]] for r in rows)
first = Counter(r[idx["分类"]].split("-")[0] for r in rows)
rep = Counter(r[idx["可复现"]] for r in rows)
overseas = [r[idx["编号"]] for r in rows if any(o in r[idx["来源渠道"]] for o in OVERSEAS)]
# 缺陷与建议怎么分，跟着「可复现」这一栏走：
# 写了发生规律的是缺陷，填「—」的是建议与主观体验。这样两栏不会互相打架。
defect = [r[idx["编号"]] for r in rows if r[idx["可复现"]] != "—"]
advice = [r[idx["编号"]] for r in rows if r[idx["可复现"]] == "—"]
raw_ch = Counter()
for r in rows:
    for c in re.split(r"[、,，/]", r[idx["来源渠道"]]):
        c = c.strip()
        if c:
            raw_ch[c] += 1

pct = lambda a, b: (a * 100.0 / b) if b else 0.0

print("待检文件：%s" % DOC)
print("表列：%s" % " | ".join(head))
print()
print("总条数：%d 条" % total)
print("按一级分类：" + "、".join("%s %d 条" % (k, v) for k, v in first.most_common()))
print("按细分分类：" + "、".join("%s %d 条" % (k, v) for k, v in cls.most_common()))
print("按可复现：" + "、".join("%s %d 条" % (k, v) for k, v in rep.most_common()))
print()
print("缺陷类 %d 条：%s" % (len(defect), "、".join(defect)))
print("建议类 %d 条：%s" % (len(advice), "、".join(advice)))
print("海外渠道参与 %d 条：%s" % (len(overseas), "、".join(overseas)))
print("海外参与占比 %.2f%%（%d / %d）" % (pct(len(overseas), total), len(overseas), total))
print("海外独立提出 %d 条：%s" % (
    len([r for r in rows if any(o in r[idx["来源渠道"]] for o in OVERSEAS)
         and not any(x in r[idx["来源渠道"]] for x in ("NGA", "TapTap", "B站"))]),
    "、".join(r[idx["编号"]] for r in rows if any(o in r[idx["来源渠道"]] for o in OVERSEAS)
              and not any(x in r[idx["来源渠道"]] for x in ("NGA", "TapTap", "B站")))))
print()
print("渠道出现次数：" + "、".join("%s %d" % (k, v) for k, v in raw_ch.most_common()))
print()
print("可复现非「—」的条目：%s" % "、".join(
    r[idx["编号"]] for r in rows if r[idx["可复现"]] != "—") or "无")
