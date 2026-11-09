# -*- coding: utf-8 -*-
"""A 数据检查 —— 数字是否有出处。

为什么查这个：交付物里的数字一旦没有出处，被追问时答不上来；
更严重的是把第三方估算当成内部数据写，内行一眼就能看出来。
"""
import re
from common import load_config, read_lines, report, write_json

NAME = "A 数据检查 — 数字与出处"

cfg = load_config()
rules = cfg["global_rules"]
num_re = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*" + rules["unit_pattern"])
src_markers = rules["source_markers"]
unc_markers = rules["uncertain_markers"]


def run():
    lines, path = read_lines()
    if lines is None:
        report(NAME, [], "未找到待检文件：%s" % path)
        write_json("A_data.json", [])
        return []

    findings = []
    seen = 0
    for idx, line in enumerate(lines, 1):
        nums = num_re.findall(line)
        if not nums:
            continue
        seen += len(nums)
        has_src = any(m in line for m in src_markers)
        has_unc = any(m in line for m in unc_markers)
        if has_src or has_unc:
            continue
        findings.append({
            "level": "待确认",
            "line": idx,
            "text": line.strip()[:90],
            "issue": "出现数字 %s，但没有来源标注，也没有标注为待验证" % "、".join(nums[:3]),
            "suggest": "补来源（官方公告／后台数据／第三方估算），或标注为待验证"
        })

    extra = "待检文件：%s\n扫描到数字 %d 处，其中 %d 处缺出处" % (path, seen, len(findings))
    report(NAME, findings, extra)
    write_json("A_data.json", findings)
    return findings


if __name__ == "__main__":
    run()
