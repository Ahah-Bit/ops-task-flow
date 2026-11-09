# -*- coding: utf-8 -*-
"""步骤 1.1：产出一份不含任何凭据的公开版页面。

原文件 人机协作流程工具/运营场景人机协作流程工具.html 一个字节都不动。
做法：复制页面与 注入密钥.py 到 公开版/，只在这一份上跑 --清空，
然后把改前改后的 size、md5、明文凭据出现次数写进 测试留档/公开版核对.json。

用法：python 准备公开版.py
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "人机协作流程工具")
SRC = os.path.join(TOOL, "运营场景人机协作流程工具.html")
DST = os.path.join(HERE, "运营场景人机协作流程工具.html")
INJECT_SRC = os.path.join(TOOL, "注入密钥.py")
INJECT = os.path.join(HERE, "注入密钥.py")
OUT = os.path.join(HERE, "测试留档", "公开版核对.json")


def md5(p):
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def size(p):
    return os.path.getsize(p)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    src_before = {"size": size(SRC), "md5": md5(SRC)}

    shutil.copy2(SRC, DST)
    shutil.copy2(INJECT_SRC, INJECT)
    dst_before = {"size": size(DST), "md5": md5(DST)}

    r = subprocess.run([sys.executable, INJECT, "--清空"], cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    print((r.stdout or "").strip())
    if r.returncode != 0:
        print("[失败] 清空脚本退出码 %d" % r.returncode)
        print((r.stderr or "")[-800:])
        return 1

    text = io.open(DST, encoding="utf-8").read()
    enc = re.search(r"var LLM_KEY_ENC = \[([^\]]*)\];", text)
    enc_items = [x for x in enc.group(1).split(",") if x.strip()] if enc else None
    plain_sk = len(re.findall(r"sk-[A-Za-z0-9_\-]{8,}", text))

    src_after = {"size": size(SRC), "md5": md5(SRC)}
    dst_after = {"size": size(DST), "md5": md5(DST)}

    rec = {
        "原文件": {"路径": "人机协作流程工具/运营场景人机协作流程工具.html",
                 "改前": src_before, "改后": src_after,
                 "未被改动": src_before == src_after},
        "公开版": {"路径": "公开版/运营场景人机协作流程工具.html",
                 "改前": dst_before, "改后": dst_after},
        "凭据核对": {"LLM_KEY_ENC_数组元素数": len(enc_items) if enc_items is not None else "未找到",
                  "明文_sk_出现次数": plain_sk,
                  "清空脚本输出": (r.stdout or "").strip()},
    }
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)

    ok = (src_before == src_after and enc_items == [] and plain_sk == 0)
    print("\n原文件未改动：%s" % rec["原文件"]["未被改动"])
    print("LLM_KEY_ENC 数组元素：%s" % rec["凭据核对"]["LLM_KEY_ENC_数组元素数"])
    print("明文 sk- 出现次数：%d" % plain_sk)
    print("核对记录：测试留档/公开版核对.json")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
