# -*- coding: utf-8 -*-
"""D 一致性检查 —— 同一个东西前后说法是否一致。

为什么查这个：同一份材料里同一个指标出现两个数，或者同一件事前后说法不同，
交出去被对方指出来，整份材料的可信度就没了。
"""
import re
from common import load_config, read_lines, report, write_json

NAME = "D 一致性检查 — 内部前后矛盾"


def run():
    cfg = load_config()
    unit = cfg["global_rules"]["unit_pattern"]
    pair_re = re.compile(
        r"([\u4e00-\u9fff]{2,8})(?:为|是|：|:)\s*([0-9]+(?:\.[0-9]+)?\s*" + unit + r")"
    )

    lines, path = read_lines()
    if lines is None:
        report(NAME, [], "未找到待检文件：%s" % path)
        write_json("D_consistency.json", [])
        return []

    bucket = {}
    for idx, line in enumerate(lines, 1):
        for m in pair_re.finditer(line):
            key = m.group(1)
            val = m.group(2).replace(" ", "")
            bucket.setdefault(key, []).append((idx, val))

    # 名称归一化：短名称若是某个长名称的子串，归到最长的那个。
    # 不加这一步，「活动期间参与率：32%」与「参与率：45%」会被当成两个指标而漏检。
    keys = list(bucket.keys())
    merged = {}
    for k, items in bucket.items():
        cands = [o for o in keys if o != k and k in o]
        canon = max(cands, key=len) if cands else k
        merged.setdefault(canon, []).extend(items)
    bucket = merged

    findings = []
    for key, items in bucket.items():
        vals = sorted(set(v for _, v in items))
        if len(vals) < 2:
            continue
        findings.append({
            "level": "需核对",
            "line": "、".join(str(i) for i, _ in items),
            "text": "%s -> %s" % (key, "、".join(vals)),
            "issue": "「%s」在文中出现了多个不同数值" % key,
            "suggest": "确认哪个为准；如果是不同口径，需在文中分别写明口径"
        })

    extra = "待检文件：%s\n提取到指标 %d 组，其中 %d 组存在多值" % (path, len(bucket), len(findings))
    report(NAME, findings, extra)
    write_json("D_consistency.json", findings)
    return findings


if __name__ == "__main__":
    run()
