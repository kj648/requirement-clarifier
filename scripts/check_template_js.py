#!/usr/bin/env python3
"""check_template_js.py — 抠出模板里的 <script> 交给 node 检查

用法:
  python3 scripts/check_template_js.py [模板路径]

为什么需要: 模板里那段 <script> 是整个页面的命脉 —— 语法一错,业务打开就是
一片空白且零提示,而 Python 侧的测试一条都照不出来。

机判两件事:
1. 语法: node --check。node 不可用则跳过并打印说明(不算失败,本地可能没装)。
2. whenToDom 契约: schema 用题号(`2=B`),DOM 用输入框 name(`q2=B`)。这个转换
   一旦静默失效,所有条件显隐/不适用/矛盾全部不匹配,页面不报错、只是什么都不发生。
   这里直接跑模板里的真实实现,不在 Python 侧镜像一份 —— 镜像就是两份真源。
"""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

TPL = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "templates" / "questionnaire.html")

# schema 题号 → DOM name 的对照;左边喂给 whenToDom,右边是期望输出
WHEN_CASES = [
    ("1=A", "q1=A"),
    ("2=B", "q2=B"),
    ("4=B & 1=B", "q4=B & q1=B"),
    ("10=C", "q10=C"),
    ("q1=A", "q1=A"),          # 已经是 DOM name,不该被二次加前缀
]


def extract_script(html: str) -> str:
    blocks = re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*type=)[^>]*>(.*?)</script>",
                        html, re.S)
    if not blocks:
        print("  ✗ 模板里找不到可检查的 <script> 块"); sys.exit(1)
    return max(blocks, key=len)


def main():
    html = TPL.read_text(encoding="utf-8")
    js = extract_script(html)
    node = shutil.which("node")
    if not node:
        print("  △ 未找到 node,跳过模板 JS 检查(CI 上 ubuntu-latest 预装 node)")
        return

    d = Path(tempfile.mkdtemp())
    f = d / "tpl.js"
    f.write_text(js, encoding="utf-8")
    r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ✗ 模板 JS 语法错误:\n{r.stderr.strip()}"); sys.exit(1)
    print(f"  ✓ 模板 JS 语法通过({len(js)} 字节)")

    # whenToDom 契约:抠出函数体单独跑,不依赖 DOM
    m = re.search(r"function whenToDom\(.*?\n\}", js, re.S)
    if not m:
        print("  ✗ 模板里找不到 whenToDom() —— 条件表达式的题号→DOM name 转换没了"); sys.exit(1)
    probe = d / "probe.mjs"
    probe.write_text(m.group(0) + "\n"
                     + f"const cases = {json.dumps(WHEN_CASES, ensure_ascii=False)};\n"
                     + "const bad = cases.filter(([i, o]) => whenToDom(i) !== o)\n"
                     + "  .map(([i, o]) => `${i} -> ${whenToDom(i)} (期望 ${o})`);\n"
                     + "console.log(JSON.stringify(bad));\n", encoding="utf-8")
    r = subprocess.run([node, str(probe)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ✗ whenToDom 探针跑不起来:\n{r.stderr.strip()}"); sys.exit(1)
    bad = json.loads(r.stdout.strip() or "[]")
    for b in bad:
        print(f"  ✗ whenToDom 契约不符: {b}")
    if bad:
        print("\n✗ 题号→DOM name 的转换失效 —— 条件显隐/不适用/矛盾会全部静默不匹配")
        sys.exit(1)
    print(f"  ✓ whenToDom 契约通过({len(WHEN_CASES)} 组)")


if __name__ == "__main__":
    main()
