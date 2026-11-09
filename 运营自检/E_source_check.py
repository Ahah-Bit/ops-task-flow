# -*- coding: utf-8 -*-
"""E 来源检查 —— 引用是否可查。

为什么查这个：引用了玩家发言、官方公告或数据却没说来自哪里，对方无法核实，
这份材料就等于没有证据支撑。运营材料里最常见的翻车点就在这里。
"""
import re
from common import load_config, read_lines, report, write_json

NAME = "E 来源检查 — 引用可查性"

# 识别四类引号：弯引号 “”、ASCII 引号、直角引号「」与双直角『』。
# 本项目统一用「」，旧规则只认前两类，所以直角引号的引用不会被扫到。
QUOTE_RE = re.compile(r"[“\"'「『]([^”\"'」』]{6,60})[”\"'」』]")


def is_name_quote(line, m, cfg):
    """版本名、活动名这类专名也会用「」包起来，但它不是引用，不需要标出处。

    判定写在 checklist.json 的 e_module_config 里，改口径不用改代码：
    引号前一段出现「版本」「副本」这类引导词，且引号后一段出现「上线」「开放」
    这类动作词，就按专名处理。两边都命中才算，避免放过真正的引用。
    这一组配置不进 global_rules，因为 global_rules 要与页面内嵌规则逐字段一致。
    """
    g = cfg.get("e_module_config", {})
    before = line[max(0, m.start() - 20):m.start()]
    after = line[m.end():m.end() + 20]
    left = any(w in before for w in g.get("quote_name_before", []))
    right = any(w in after for w in g.get("quote_name_after", []))
    return left and right


def run():
    cfg = load_config()
    src_markers = cfg["global_rules"]["source_markers"]

    lines, path = read_lines()
    if lines is None:
        report(NAME, [], "未找到待检文件：%s" % path)
        write_json("E_source.json", [])
        return []

    findings = []
    total_quotes = 0
    for idx, line in enumerate(lines, 1):
        if any(m in line for m in src_markers):
            continue
        quotes = []
        for m in QUOTE_RE.finditer(line):
            total_quotes += 1
            if is_name_quote(line, m, cfg):
                continue
            quotes.append(m.group(1))
        if not quotes:
            continue
        findings.append({
            "level": "待确认",
            "line": idx,
            "text": line.strip()[:90],
            "issue": "引用了「%s」，但同一行没有来源标注" % quotes[0][:30],
            "suggest": "补出处（平台／帖子／公告名或链接），确保能被查证"
        })

    extra = "待检文件：%s\n扫描到引用 %d 处，其中 %d 处缺来源" % (path, total_quotes, len(findings))
    report(NAME, findings, extra)
    write_json("E_source.json", findings)
    return findings


if __name__ == "__main__":
    run()
