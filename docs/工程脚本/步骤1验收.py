# -*- coding: utf-8 -*-
"""步骤 1 验收：把散在各处的证据收成一份可独立复核的清单。

不自己算数，全部读实际文件与测试 log。用法：python 步骤1验收.py
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "人机协作流程工具")
SELF = os.path.join(ROOT, "运营自检")
ORIG = os.path.join(TOOL, "运营场景人机协作流程工具.html")
PUB = os.path.join(HERE, "运营场景人机协作流程工具.html")
LOGS = os.path.join(HERE, "测试留档")
EXPECT_MD5 = "f630f63f70b6a99c98723bf0262c4730"
EXPECT_SIZE = 314444


def md5(p):
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def read(p):
    return io.open(p, encoding="utf-8").read()


def main():
    checks = []

    def ck(label, ok, detail=""):
        checks.append({"项": label, "通过": bool(ok), "实测": detail})

    # 1 原文件：架构未动
    size, h = os.path.getsize(ORIG), md5(ORIG)
    ck("工具原文件 size 314444", size == EXPECT_SIZE, str(size))
    ck("工具原文件 md5 未变", h == EXPECT_MD5, h)

    # 2 公开版：无凭据
    pub = read(PUB)
    enc = re.search(r"var LLM_KEY_ENC = \[([^\]]*)\];", pub)
    items = [x for x in enc.group(1).split(",") if x.strip()] if enc else ["未找到"]
    sk = len(re.findall(r"sk-[A-Za-z0-9_\-]{8,}", pub))
    ck("公开版 LLM_KEY_ENC 已清空", items == [], str(items))
    ck("公开版明文 sk- 为 0", sk == 0, str(sk))

    # 3 六套测试
    summ = json.loads(read(os.path.join(LOGS, "汇总.json")))
    bad = [t["name"] for t in summ["tests"] if t["exit"] != 0]
    ck("六套测试全部退出码 0", not bad, "、".join(bad) or "6/6")
    for t in summ["tests"]:
        ck("　" + t["name"] + " 退出码 0", t["exit"] == 0, "%s，%.1f 秒" % (t["exit"], t["seconds"]))

    # 4 两份负向测试
    n1 = read(os.path.join(LOGS, "负向测试-v332.py.log"))
    n2 = read(os.path.join(LOGS, "负向测试-泳道图布局.py.log"))
    ck("负向测试 v3.32 拦住 4/4 并还原", "4 / 4 组被拦住" in n1 and "md5 与动手前一致 True" in n1,
       [l.strip() for l in n1.splitlines() if "负向测试结果" in l][:1])
    ck("负向测试 泳道图 拦住 4/4 并还原", "拦住 4/4" in n2 and "还原后内容一致：是" in n2,
       [l.strip() for l in n2.splitlines() if "结果：拦住" in l][:1])

    # 5 三条 bug 的落地证据
    ck("口径：公开版提示词写「—」", "一律写「—」" in pub, "公开版 TAG_P2")
    cfg = json.loads(read(os.path.join(SELF, "checklist.json")))
    ck("口径：规则库同口径", "非缺陷类填「—」" in cfg["deliverable_types"]["feedback_table"]["notes"], "checklist.json")
    e_src = read(os.path.join(SELF, "E_source_check.py"))
    e_rec = json.loads(read(os.path.join(LOGS, "E模块核对.json")))
    ck("E 模块识别直角引号", "「『" in e_src and e_rec["旧规则报出条数"] == 0 and e_rec["新规则报出条数"] == 1,
       "旧规则 %d 条，新规则 %d 条" % (e_rec["旧规则报出条数"], e_rec["新规则报出条数"]))
    ck("E 模块回归后 39/39 且零误报",
       e_rec["eval_注入"] == 39 and e_rec["eval_检出"] == 39 and e_rec["eval_疑似误报"] == 0,
       "%d/%d，误报 %d" % (e_rec["eval_检出"], e_rec["eval_注入"], e_rec["eval_疑似误报"]))
    chain = os.path.join(TOOL, "校准材料", "跑全链-页面代码.py")
    r = subprocess.run([sys.executable, chain, "--只取提示词"], cwd=os.path.dirname(chain),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    ck("全链脚本离线取值链路通过", r.returncode == 0 and "离线取值链路：通过" in (r.stdout or ""),
       (r.stdout or "").strip().splitlines()[-1] if (r.stdout or "").strip() else "")

    out = {"验收项": checks,
           "全部通过": all(c["通过"] for c in checks),
           "原文件": {"size": size, "md5": h},
           "公开版": {"LLM_KEY_ENC_元素数": len(items) if items != ["未找到"] else "未找到", "明文_sk": sk}}
    with io.open(os.path.join(LOGS, "步骤1验收.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    for c in checks:
        print(("  [通过] " if c["通过"] else "  [失败] ") + c["项"] +
              ("　" + str(c["实测"]) if c["实测"] else ""))
    print("\n步骤 1 验收：" + ("全部通过" if out["全部通过"] else "有未通过项"))
    return 0 if out["全部通过"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
