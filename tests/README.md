## 两类测试

- **`test_*.py`** — 可执行断言，CI 每次 push/PR 跑（`python3 -m unittest discover -s tests`）。
  覆盖：questionnaire.json 校验、样例数据、HTML/MD 渲染、回执机检。
- **`scenario-*.md`** — 给人读的场景剧本，用来人工回归 skill 的**判断质量**
  （成色分级、冲突检测、剥离阀门）——这些没法用断言表达，需要人读产出评估。

- **`scripts/check_template_js.py`** — 抠出模板里的 `<script>` 跑 `node --check`，并用
  node 跑模板里真实的 `whenToDom()` 核对「schema 题号 → DOM name」的转换。这两件事
  Python 测试照不出来：语法一错业务看到空白页且零提示；转换一失效条件显隐/不适用/矛盾
  全部静默不匹配。

**CI 覆盖不到的**：模板的**渲染结果与视觉**需要浏览器（语法与 whenToDom 已由上面那条覆盖）。
每次改 `templates/questionnaire.html` 后按实施计划 Task 3 Step 6 的清单人工过一遍。

## `build_questionnaire.py` 的 `--root`

`rules_ref.doc` 是相对项目根解析的路径。`--root` 默认**不需要**手动传——会从
`<questionnaire.json>` 的位置往上找含 `docs/requirements/` 的那一层，自动当作项目根
（`infer_root()`，`scripts/build_questionnaire.py`）。只有 questionnaire.json 不在项目内
（脱离 `docs/requirements/` 目录结构）的特殊场合才需要显式传 `--root`。

```bash
python3 scripts/build_questionnaire.py \
  examples/demo-project/docs/requirements/questionnaires/2026-07-11-报销打款-r1.json --check
python3 scripts/build_questionnaire.py \
  examples/demo-project/docs/requirements/questionnaires/2026-07-11-报销打款-r1.json -o /tmp/confirm.html
```

# 压测场景:判断题规则的回归测试

`verify_evidence.py` / `check_questionnaire.py` 管得住**机械约束**,但 skill 里最值钱的是**判断题规则**(信源分级、环境自检、回答验收)——它们无法用 regex 强制,只能用压力场景验证。本目录借用 [superpowers](https://github.com/obra/superpowers) 的思路:**写 skill 就是对流程文档做 TDD**。

## RED-GREEN 工作流

| TDD | 对应操作 |
|---|---|
| 测试先行(RED) | 把场景 prompt 喂给**未加载本 skill** 的新对话,记录它如何违规、用什么话术自我合理化 |
| 实现(GREEN) | 同一 prompt 喂给**加载了本 skill** 的新对话,对照判定清单逐项打分 |
| 重构 | 发现新的合理化话术 → 补进 SKILL.md 对应规则 → 重跑场景确认仍通过 |

**每次修改 SKILL.md 的判断题段落(铁律 3、阶段一分级、阶段三验收、模式 B 第 0 步),发版前至少重跑涉及的场景。** 判定清单里任何一项从过变不过,就是回归。

## 运行方式

- **基线(RED)**:新开一个不含本 skill 的会话(或明确指示"不要调用任何 skill"),粘贴场景文件中的『场景 prompt』,原样记录回答。
- **合规(GREEN)**:在装有本 skill 的环境新开会话,粘贴同一 prompt,按『判定清单』逐项勾选。
- 用 subagent 跑更省事:主会话把 prompt 派给一个干净子代理即可;注意基线子代理要禁用 skill 调用。

## 场景清单

| 文件 | 压的是哪条规则 | 典型违规 |
|---|---|---|
| [scenario-1-source-tiering.md](scenario-1-source-tiering.md) | 铁律 3 + 阶段一信源分级 | 拿开发者的架构理解覆盖需求方 Excel |
| [scenario-2-env-selfcheck.md](scenario-2-env-selfcheck.md) | 模式 B 第 0 步环境自检 | 无代码库时编造"现有页面"的字段和行为 |
| [scenario-3-dirty-receipt.md](scenario-3-dirty-receipt.md) | 阶段三验收答案 | 混入的新需求被无声合并;"看着办"被当成授权 |

## 判分标准

每个场景的判定清单为二值项(过/不过),**全过才算 GREEN**。部分通过说明规则文本有漏洞——把该次违规的原话记进场景文件的『已知合理化话术』,然后修 SKILL.md。
