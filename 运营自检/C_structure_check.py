# -*- coding: utf-8 -*-
"""C 结构检查 —— 该有的栏目有没有缺。

为什么查这个：漏项是交付物被打回的头号原因。原始要求里逐项列出的维度，
只要有一条没有显式落地，交出去就是缺项。
"""
from common import load_config, read_lines, report, write_json

NAME = "C 结构检查 — 栏目覆盖"


def run():
    cfg = load_config()
    dtype = cfg.get("target_type", "")
    spec = cfg["deliverable_types"].get(dtype, {})
    required = spec.get("required_sections", [])

    lines, path = read_lines()
    if lines is None:
        report(NAME, [], "未找到待检文件：%s" % path)
        write_json("C_structure.json", [])
        return []

    text = "\n".join(lines)
    findings = []
    for sec in required:
        if sec in text:
            continue
        findings.append({
            "level": "缺项",
            "line": "-",
            "text": sec,
            "issue": "该类型交付物要求的栏目「%s」在文件中未出现" % sec,
            "suggest": "补上这一栏；若本单确实不涉及，补一句说明为什么不涉及"
        })

    extra = "待检文件：%s\n交付物类型：%s\n必含栏目 %d 项，缺失 %d 项" % (
        path, spec.get("name", dtype), len(required), len(findings))
    report(NAME, findings, extra)
    write_json("C_structure.json", findings)
    return findings


if __name__ == "__main__":
    run()
