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


def extract_fn(js, name):
    """按括号计数截出一个函数,不多不少 —— 单行/多行都对。

    别用 `function name\\(.*?\\n\\}` 那种正则:单行实现的函数闭合括号不在独立行上,
    非贪婪匹配会一路吃到下一个函数的结尾,把别人的函数体也拖进探针里(实测踩过 ——
    whenToDom 是单行实现,曾把紧跟其后的 questionHtml 整个函数体一起抠出来)。

    已知局限:括号计数不解析字符串/正则/注释里的花括号,如果目标函数体内出现含
    `{`/`}` 的字符串字面量或正则,截取会错。当前 whenToDom 的实现只是一行
    `String(expr).replace(/…/g, '$1q$2')`,不含花括号,所以安全;真要变复杂时
    应改用真正的 JS 解析器,而不是在这里加更多补丁。
    """
    i = js.find(f"function {name}(")
    if i < 0:
        return None
    depth = 0
    for k in range(js.index("{", i), len(js)):
        if js[k] == "{":
            depth += 1
        elif js[k] == "}":
            depth -= 1
            if depth == 0:
                return js[i:k + 1]
    return None


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
    print(f"  ✓ 模板 JS 语法通过({len(js)} 字符)")

    # whenToDom 契约:抠出函数体单独跑,不依赖 DOM
    fn = extract_fn(js, "whenToDom")
    if not fn:
        print("  ✗ 模板里找不到 whenToDom() —— 条件表达式的题号→DOM name 转换没了"); sys.exit(1)
    # 自检:抠多了就直接报,别让探针带着别人的函数体跑
    if fn.count("function ") > 1:
        print("  ✗ 抠出的 whenToDom 里含第二个 function —— 截多了,探针跑的不是它自己"); sys.exit(1)
    if not fn.endswith("}"):
        print("  ✗ 抠出的 whenToDom 没有闭合 —— 括号计数没截到底"); sys.exit(1)
    probe = d / "probe.mjs"
    probe.write_text(fn + "\n"
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
