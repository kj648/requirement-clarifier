# Requirement Clarifier（需求澄清器）

**把模糊需求变成可验证、可追溯、可直接开工的开发规格。**

一套给 AI coding agent 用的需求工程工作流——Claude Code、OpenCode、Codex、Cursor 以及任何认 `SKILL.md` 约定的平台。它的职责是：**在需求还没说清之前，拦住你的 agent（和你自己）直接开始写代码。**

[![CI](https://github.com/kj648/requirement-clarifier/actions/workflows/ci.yml/badge.svg)](https://github.com/kj648/requirement-clarifier/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/kj648/requirement-clarifier)](https://github.com/kj648/requirement-clarifier/releases)

**[English README →](README.md)**

---

## 它解决什么问题

你把一段模糊需求丢给 coding agent——业务方的微信语音、群聊碎片、只写了正常流程的 PRD——agent **立刻开始写代码**。每一条没说清的规则都变成一个悄悄写死在实现里的猜测。几周后："我没说过要这样。"

## 它怎么做

```text
原始需求（口述 / 群聊 / 模糊 PRD / 老 Excel）
      ↓
输入分级          —— 哪些是需求方的事实，哪些是开发自己的推断
      ↓
盲区挑漏洞        —— 12 维清单：权限、状态、并发、存量迁移、金额口径……
      ↓
可交互确认单      —— 单文件 HTML，业务点选即填；每道题带自己的依据
      ↓
验收答案          —— 成色分级、与旧决定的冲突检测、剥离混进来的新需求
      ↓
可追溯规格        —— 每条决定带【业务确认】/【开发拟定】/【假设】标签，
      ↓              背后有签过字的回执
证据核验 + CI     —— 引用逐条机检，断链即 FAIL
```

**填单的人不需要懂 markdown、git 或 AI。** 他拿到的是一个双击就能开的 HTML 文件——离线、内网、微信里都能打开——填完导出一份可机检的回执发回来。

## 十秒版

**进** —— 运营的一句语音：

> "报销单审批通过后系统自动打款，不要再靠财务翻表逐单人工发起。"

**出** —— 在写任何代码之前，把没人说过的事挑出来：

```text
4 道业务必须先定的题：
  Q1  「可打款」从哪个节点算——审批通过即可，还是要财务复核？        [阻塞]
  Q3  报销单被部分驳回（只批了一部分金额），照打还是转人工？
      ⚠ 无据 —— 这个场景没人提过，业务可一键判「不成立」
  Q2×Q3 填写现场抓到矛盾：「每天自动批量打款」撞上「部分驳回转人工」
      —— 挂在人工队列的单子会不会被自动批次捞走？

产出规格：【业务确认】×3 ·【开发拟定】×3 ·【假设】×4
每一条都能追溯到签过字的回执
```

## 长什么样

生成的确认单——记账凭证纸质感、进度条、「我们理解的」逐条三态核对：

![确认单](docs/assets/questionnaire-hero.png)

每道题带**依据档位**。没有任何来源的题公开标红为「无据 · 请证伪」，给一键「这种情况不存在」的出口；演示数字随业务的点选实时点亮对应分支：

![依据三档与证伪出口](docs/assets/questionnaire-evidence.png)

## 经过测试，不只是写了段 Prompt

大多数 agent skill 的本质是「作者觉得这样写有效」。这个仓库自带 harness：

- ✅ **133 条回归测试**（纯 Python 标准库 `unittest`，零第三方依赖）
- ✅ **证据核验**——每条 `> 证据: 路径:行号 | "原文片段"` 引用逐条对照源文件，断链即 FAIL
- ✅ **确认单契约校验**——依赖悬空、分支不对称、规则题带建议措辞、阻塞题缺演示数字：出包前全部拒收
- ✅ **回执机检**——阻塞题未答、未署名、矛盾未说明，在答案被合并之前拦住
- ✅ **模板 JS 语法 + 契约探针**——交互单的脚本在 CI 里被抠出来检查，因为语法一错业务看到的就是白屏
- ✅ **每次 push 跑 7 步 CI 门禁**

## 安装

**最短路径**（经 [skills](https://www.npmjs.com/package/skills) 安装器，支持 Claude Code、OpenCode、Codex、Cursor 等 17 种 harness）：

```bash
npx skills add kj648/requirement-clarifier
```

加 `-g` 装全局，不加装当前项目。

**手动 clone：**

```bash
git clone https://github.com/kj648/requirement-clarifier.git \
  ~/.claude/skills/requirement-clarifier          # Claude Code
# 或 ~/.config/opencode/skills/…                  # OpenCode
# 或 ./.agents/skills/…                           # 通用
```

**或者**从 [Releases](https://github.com/kj648/requirement-clarifier/releases) 下载 `requirement-clarifier.skill` 导入。

## 快速开始

在 Agent 对话中输入：

> "业务方说想加一个审批功能，让我理一下需求。"

Agent 会按 skill 指示：

1. 将原始需求逐字归档到 `docs/requirements/raw/`
2. 对照 `docs/requirements/context.md` 翻译业务黑话
3. 读盲区清单挑漏洞，生成 `questionnaire.json` 并出单文件 HTML 确认单
4. 你把单子发给能拍板的人；回执带回后，机检 → 成色分级 → 冲突检测 → 生成 `docs/requirements/specs/<功能>.md`

## 工作模式

**核心闭环只有一个模式——新需求澄清。** 模糊需求进，盲区问题出，业务确认，可追溯规格落地。从它开始。

| 核心 | 触发语 | 输出 |
|---|---|---|
| A. 新需求澄清 | "帮我理一下这个需求" | 问题清单 + HTML 确认单 + 开发规格 |

其余是用熟之后的进阶模式：

| 进阶 | 触发语 | 输出 |
|---|---|---|
| B. 需求变更 | "业务说要改 XX" | 影响分析 + 更新规格 + 返工代价确认单 |
| C. 上下文维护 | "记一下，'单子'指采购单" | 更新 `context.md` |
| D. 链路审计 | "审计一下 XX 链路有没有坑" | 状态×操作组合矩阵 + 问题清单 + 修复项 |
| 逆向场景 | "把这个老 Excel 搬进新系统" | 规则文档（owner 勾选验真）+ 对数回归 |

## 与 grill-me 类技能的分界

「拷问你的计划」类 skill（grill-me、brainstorming……）拷问的是**开发者自己**——推荐答案是加速，猜错了自己担。本 skill 的产出面向**没写过 prompt 的第三方**：

- **规则／账务口径题永不预选、永不标建议**——在「『可打款』从哪个节点算起」上预勾一个默认值，等于开发替业务拍板，还让业务签了字
- **每道题带依据**（原话引用／代码引用／公开标注「无据」），无据题给证伪出口，而不是逼人在错的选项里挑一个
- **每个演示数字按分支各算一遍**——业务比较的是 70.0% vs 63.6% vs 50.0%，不是抽象口径
- **回执是溯源凭证**：署名、日期、机检、归档

## 完整走查案例

[`examples/demo-project`](examples/) 是一个可以亲手跑的缩微闭环：一句微信语音原话 → 盲区挑漏洞 → 一份带脏答案的回执（混进新需求、"你看着办"落为【开发拟定】）→ 一份通过证据核验的规格。所有 harness 脚本都能在案例上直接运行。

## 目录结构

```
requirement-clarifier/
├── SKILL.md                          # skill 主文件（五条铁律 + 模式 + 证据纪律）
├── scripts/
│   ├── build_questionnaire.py        # questionnaire.json → HTML/md 确认单（校验不过不出包）
│   ├── check_questionnaire.py        # 回执机检（九件事）
│   ├── verify_evidence.py            # 证据核验 harness
│   ├── check_template_js.py          # 模板 JS 语法 + whenToDom 契约探针（CI 用）
│   └── validate_skill.py             # frontmatter 校验
├── references/
│   ├── blindspot-checklist.md        # 盲区清单（12 维）
│   ├── questioning-rules.md          # 出题规则（生成确认单前必读）
│   ├── chain-audit-checklist.md      # 链路审计方法
│   └── cold-start.md                 # 存量材料批量导入
├── templates/
│   ├── questionnaire.html            # 确认单 HTML 模板（自包含，离线可用）
│   ├── questionnaire.schema.json     # 题目数据字段契约
│   ├── questionnaire-template.md     # 由 json 生成的 md 示例
│   ├── rules-template.md             # 逆向规则文档骨架
│   ├── context-template.md / spec-template.md / confirmation-template.md
├── tests/                            # 133 条回归测试 + golden fixtures
├── examples/demo-project/            # 完整走查案例
└── .github/workflows/                # ci.yml（7 步门禁）+ release.yml
```

## 证据纪律

所有引用来源的产出使用自证引用格式：

```markdown
> 证据: docs/requirements/raw/2026-07-14-prd.md:12 | "业务方原话片段"
```

交付前运行：

```bash
python3 scripts/verify_evidence.py <产出文件> --root .
```

严格模式下无主数值直接 FAIL：加 `--strict`。

## 许可证

[PolyForm Noncommercial 1.0.0](LICENSE)。允许学习、修改、个人与内部使用；**禁止商用**。商用授权请联系作者。

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。提交 PR 前：`python3 -m unittest discover -s tests -p 'test_*.py'` 全绿、不带 `__pycache__/`。
