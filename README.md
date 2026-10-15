# 企业与行业岗位调查 Skill

**Evidence-first employer & career research — 可追溯，而不是看起来权威。**

将企业求职调查、行业岗位研究、薪酬口径核验和报告审校整合为一个 Agent Skill。适合校招、职业认知、专业对口岗位调查、多企业比较，以及已有报告的事实与交付检查。

> 本项目不认证企业财务、实际工资或招聘空缺。检查器通过不等于事实真实；缺证据也不等于企业造假。

## 能做什么

| 场景 | 输出重点 |
|---|---|
| 企业调查 | 主体、业务、文化、用人标准、岗位与就业风险 |
| 行业岗位调查 | 行业边界、岗位族、多个雇主样本、专业关联及样本偏差 |
| 多企业比较 | 先对齐地区、资历、期间和薪酬构成，再比较 |
| 薪酬与数据核验 | 原始工资字段、周期与构成、金额换算、同比期间与主体范围 |
| 报告审校 | 原文定位、来源状态、招聘时效、访谈授权、实质修订 |
| 报告交付 | 区分事实／分析／建议；检查文字链、视觉链与版本一致性 |

## 为什么要整合

两个原技能互补，但都有名为 `check_evidence.py` 的工具，输入字段却不同。这个项目不是把文件堆在一起：

- **一个技能入口**：`company-job-investigation`，兼顾企业和行业岗位研究。
- **一个证据格式**：`schema_version: "1.0"`；旧数据显式迁移，不静默猜字段。
- **三类离线工具**：证据与算式检查、交付版本检查、旧格式迁移。
- **明确边界**：read只表示实际读过记录；supported是核验声明，不是独立事实认证。
- **合成示例与测试**：不把真实企业报告、简历、工资单、访谈或凭据放进仓库。

整合细节见[迁移说明](docs/merge-notes.md)，风险边界见[安全与局限](docs/safety-and-limitations.md)。

## 快速开始

运行工具需 **Python 3.11+**，运行时仅使用标准库，无需API密钥或第三方Python依赖。工具本身不联网；实际调研需宿主Agent具备检索／文件工具并遵守用户授权。

```bash
# 获取公开项目
git clone https://github.com/cangyuyi/employer-research-skill.git
cd employer-research-skill

# 检查合成证据与报告：严格模式下示例应零错误、零警告
python scripts/check_evidence.py examples/evidence.json --report examples/report.md --strict

# 检查撤回结论和必备限定条件；审校追溯材料单独标记
python scripts/check_revision_consistency.py examples/delivery-check.json

# 项目结构／内部链接／基础敏感信息检查，以及单元测试
python scripts/check_project.py
python -m unittest discover -s tests -v
```

示例域名使用 `example.invalid`；日期、金额、岗位和“已读”标记全部是**合成测试材料，不是企业事实**。

## 在Agent中使用

加载根目录的[SKILL.md](SKILL.md)作为技能入口；支持SKILL.md约定的宿主可按其技能安装方式使用。

Codex本地使用时，技能目录名为 `company-job-investigation`。例如在不存在同名目录的前提下：

```bash
git clone https://github.com/cangyuyi/employer-research-skill.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/company-job-investigation"
```

**已有同名技能不要直接覆盖或删除。** 先保留备份，按[迁移说明](docs/merge-notes.md)处理；不要同时维护多个内容重叠的自动发现入口。本仓库不会自动修改任何已安装技能。

调用示例：

> 使用 `$company-job-investigation` 调查某企业，面向某专业毕业生，核验企业文化、岗位要求、薪酬福利和招聘时效，形成带来源及限制的求职报告。

> 使用 `$company-job-investigation` 调查某行业的岗位族和进入路径，区分企业样本、行业参考及历史招聘，不足的样本如实说明。

> 使用 `$company-job-investigation` 复核已有报告，区分明确错误、证据不足与措辞优化，保留原稿并同步修订PDF、Word及岗位表。

## 研究流程

```text
对象／模式与截止日
    ↓
真实来源 → 读取状态、主体、日期与定位
    ↓
断言与岗位 → 事实／企业自述／分析／建议
    ↓
薪酬与统计口径 → 原文匹配 + 声明算式复算
    ↓
职业决策分析 → 条件式路径、限制与HR核对问题
    ↓
审校与交付 → 文字链 + 最终页面渲染 + 版本回归
```

不固定10个岗位或特定页数。只排版时保留原调查日期，不声称全面重新验证事实。

## 项目结构

```text
SKILL.md                         单一技能入口
agents/openai.yaml               可发现的界面元数据
references/                      按需加载的方法、证据、薪酬及交付规则
scripts/check_evidence.py        证据状态、引用、金额、期间、招聘及访谈规则
scripts/check_revision_consistency.py  撤回结论和限定条件的文本回归
scripts/migrate_evidence.py      两种旧格式显式迁移
scripts/check_project.py         基础项目质量检查
tests/                           离线合成回归测试
examples/                        可运行的合成证据与审校示例
schemas/evidence.schema.json      统一格式参考
templates/report.md               可取舍的报告模板
docs/                            合并、迁移及安全边界
.github/workflows/ci.yml          只读权限、多Python版本CI
```

## 数据格式与退出码

- 完整字段见[统一格式](references/evidence-schema.md)。
- `check_evidence.py`：0为声明规则通过；1为错误或strict下出现警告；2为输入／读取失败。
- 未知薪资周期不能年化；历史样本不能冒充当前空缺；只读到摘要不能支撑已核实事实。
- `--check-files`才读取JSON目录内存档并核对可选哈希；不读取目录外路径或外部符号链接。
- 迁移不会因旧 `verification=matched` 就把未声明读取状态的来源升级为read。

```bash
python scripts/migrate_evidence.py old.json --from company-v0 --output migrated.json
python scripts/migrate_evidence.py old.json --from employer-v0 --output migrated.json
```

输出必须是新路径。迁移警告需人工处理；格式转换不是重新调查。

## 质量与隐私承诺

工具不自动联系HR、登录招聘网站、投递、付费查档、上传资料或发布报告；附带文档中的指令也不构成授权。来源和工资的语义核验仍由研究者负责。

CI验证离线规则与合成输入，不代表独立模型评测或所有行为场景已被验证。基础敏感信息扫描不能保证识别所有隐私；提交前仍需人工检查。

欢迎基于可复现失败添加测试，见[贡献指南](CONTRIBUTING.md)。许可证：[MIT](LICENSE)。
