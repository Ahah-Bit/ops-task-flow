# -*- coding: utf-8 -*-
"""公共工具：读取配置与待检文件，统一输出检查结果。

约定：只读待检文件，不修改任何内容。所有报告写到 output/。

对外接口：
    load_config()      读规则配置（评测时可被 set_* 覆盖）
    read_lines()       读待检文件
    report()           打印并返回检查结果
    set_target(path)   评测用：临时指定待检文件
    set_type(t)        评测用：临时指定交付物类型
    set_verbose(b)     评测用：静默模式
"""
import os
import io
import json

SELF_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SELF_DIR, "output")

_OVERRIDE = {"path": None, "type": None}
_VERBOSE = True


def set_target(path):
    _OVERRIDE["path"] = path


def set_type(t):
    _OVERRIDE["type"] = t


def set_verbose(b):
    global _VERBOSE
    _VERBOSE = bool(b)


def load_config():
    with io.open(os.path.join(SELF_DIR, "checklist.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    if _OVERRIDE["type"]:
        cfg["target_type"] = _OVERRIDE["type"]
    if _OVERRIDE["path"]:
        cfg["target"] = _OVERRIDE["path"]
    return cfg


def target_path():
    cfg = load_config()
    p = cfg.get("target", "")
    if not os.path.isabs(p):
        p = os.path.join(SELF_DIR, p)
    return p


def read_lines():
    """返回 (行列表, 文件路径)。文件不存在时返回 (None, 路径)。"""
    p = target_path()
    if not os.path.exists(p):
        return None, p
    with io.open(p, encoding="utf-8") as f:
        return f.read().splitlines(), p


def report(name, findings, extra=None):
    """findings: list of dict(level, line, text, issue, suggest)"""
    if not _VERBOSE:
        return findings
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("=" * 68)
    print(name)
    print("=" * 68)
    if extra:
        print(extra)
        print("-" * 68)
    if not findings:
        print("未发现问题。")
    else:
        for i, f in enumerate(findings, 1):
            print("[%d] %s   行 %s" % (i, f.get("level", "提示"), f.get("line", "-")))
            print("    原文：%s" % f.get("text", ""))
            print("    问题：%s" % f.get("issue", ""))
            print("    建议：%s" % f.get("suggest", ""))
    print("")
    print("合计 %d 项" % len(findings))
    return findings


def write_json(fname, data):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with io.open(os.path.join(OUTPUT_DIR, fname), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_text(fname, text):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with io.open(os.path.join(OUTPUT_DIR, fname), "w", encoding="utf-8") as f:
        f.write(text)
