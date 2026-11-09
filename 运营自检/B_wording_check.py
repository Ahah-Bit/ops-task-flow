# -*- coding: utf-8 -*-
"""B 表述检查 —— 禁用表述与套话。

为什么查这个：公告与宣发文案里的绝对化用语、承诺性表述会带来合规风险；
空泛的套话则让读者看不到具体信息，运营原文要求"保证信息准确"。
"""
from common import load_config, read_lines, report, write_json

NAME = "B 表述检查 — 禁用表述与套话"


def run():
    cfg = load_config()
    dtype = cfg.get("target_type", "")
    spec = cfg["deliverable_types"].get(dtype, {})
    forbidden = spec.get("forbidden_wording", [])
    soft = spec.get("soft_wording", [])

    lines, path = read_lines()
    if lines is None:
        report(NAME, [], "未找到待检文件：%s" % path)
        write_json("B_wording.json", [])
        return []

    findings = []
    for idx, line in enumerate(lines, 1):
        for w in forbidden:
            if w in line:
                findings.append({
                    "level": "需修改",
                    "line": idx,
                    "text": line.strip()[:90],
                    "issue": "出现禁用表述「%s」" % w,
                    "suggest": "改为可核实的客观描述，避免绝对化与承诺性表述"
                })
        for w in soft:
            if w in line:
                findings.append({
                    "level": "建议",
                    "line": idx,
                    "text": line.strip()[:90],
                    "issue": "出现空泛表述「%s」" % w,
                    "suggest": "换成具体信息，例如具体数值、具体变化或具体要求"
                })

    extra = "待检文件：%s\n交付物类型：%s\n禁用词 %d 个，软性词 %d 个" % (
        path, spec.get("name", dtype), len(forbidden), len(soft))
    report(NAME, findings, extra)
    write_json("B_wording.json", findings)
    return findings


if __name__ == "__main__":
    run()
