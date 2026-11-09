# -*- coding: utf-8 -*-
"""F 列举检查 —— 「N 条」跟后面实际列了几项是否对得上。

为什么查这个：实测里同一类错出现过两次——稿子写「共 4 条」，后面却列了 5 个。
原有的五个模块都查不到：A 查数字有没有出处，D 查同一指标有没有两个值，
都不管「数字与紧随其后的枚举数量是否一致」。

这类错不需要判断力，数一遍就行，正好交给机器。

两类写法都查：
    ① 同一行「… 4 条，包括：A（序号 1）、B（序号 2）…」
    ② 一行以「… 1 条（来源：本期分类表）：」收尾，下面跟两个以上列表项
"""
import re
from common import read_lines, report, write_json

NAME = "F 列举检查 — 数量与枚举是否对得上"

# 「N 条」。注意稿子里常写成 **4** 条，所以要先把 Markdown 加粗标记去掉再匹配
CNT_RE = re.compile(r"(\d+)\s*条")
LEAD_WORDS = ("包括", "如下", "分别是", "分别为")
TAIL_RE = re.compile(r"(\d+)\s*条[^。！？\n]{0,22}[：:]\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-*·]|\d+[.、)])\s+\S")
# 段子里自带的「N 条」——出现它说明这是分类明细，不是逐条列举
INNER_CNT_RE = re.compile(r"\d+\s*条")


def _plain(s):
    """去掉 Markdown 加粗标记，只用于匹配，报出时仍用原文。"""
    return s.replace("**", "").replace("__", "")


def _lead_pos(tail):
    best = -1
    for w in LEAD_WORDS:
        p = tail.find(w)
        if p > -1 and (best < 0 or p < best):
            best = p
    return best


def _count_items(seg):
    """数一段里列了几项。优先数「序号」出现次数（最稳），否则按顿号逗号切。"""
    if seg.count("序号") >= 2:
        return seg.count("序号")
    return len([p for p in re.split(r"[、，,；;]", seg) if p.strip()])


def run():
    lines, path = read_lines()
    if lines is None:
        report(NAME, [], "未找到待检文件：%s" % path)
        write_json("F_enum_count.json", [])
        return []

    findings = []
    scanned = 0

    # 模式一：同一行里「N 条 … 包括：A、B、C」
    for idx, line in enumerate(lines, 1):
        cl = _plain(line)
        m = CNT_RE.search(cl)
        if not m:
            continue
        tail = cl[m.end():]
        pos = _lead_pos(tail)
        if pos < 0:
            continue
        scanned += 1
        n = int(m.group(1))
        seg = tail[pos:].split("。")[0]
        for w in LEAD_WORDS:
            if seg.startswith(w):
                seg = seg[len(w):]
                break
        seg = seg.lstrip("：:，, ")
        if INNER_CNT_RE.search(seg):      # 分类明细，不是逐条列举
            continue
        cnt = _count_items(seg)
        if cnt >= 2 and cnt != n:
            findings.append({
                "level": "待确认",
                "line": idx,
                "text": line.strip()[:90],
                "issue": "这一行写「%d 条」，按后面列出的项算是 %d 项，两个数对不上" % (n, cnt),
                "suggest": "数一遍，把数字改对；或者把多出来／少掉的条目补齐"
            })

    # 模式二：一行以「N 条…：」收尾，下面跟两个以上列表项
    for i, line in enumerate(lines):
        cl = _plain(line)
        m = TAIL_RE.search(cl)
        if not m:
            continue
        scanned += 1
        n = int(m.group(1))
        j, items = i + 1, []
        while j < len(lines) and BULLET_RE.match(lines[j]):
            items.append(lines[j])
            j += 1
        if len(items) < 2:
            continue
        if any(INNER_CNT_RE.search(_plain(b)) for b in items):
            continue
        if len(items) != n:
            findings.append({
                "level": "待确认",
                "line": i + 1,
                "text": line.strip()[:90],
                "issue": "这一行写「%d 条」，下面列了 %d 个条目，两个数对不上" % (n, len(items)),
                "suggest": "数一遍，把数字改对；或者把多出来／少掉的条目补齐"
            })

    extra = "待检文件：%s\n扫描到带列举的「N 条」%d 处，其中 %d 处与枚举数量对不上" % (path, scanned, len(findings))
    report(NAME, findings, extra)
    write_json("F_enum_count.json", findings)
    return findings


if __name__ == "__main__":
    run()
