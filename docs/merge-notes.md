# 整合与迁移说明

## 统一而不是简单拼接

合并来源为用户提供的 `company-job-investigation`、`employer-research` 两套技能及前者最近审校增强版。只保留一个入口 `company-job-investigation`，项目仓库命名为 `employer-research-skill`；不分发另一套竞争触发的SKILL.md。

| 原能力 | 合并后的归属 |
|---|---|
| 企业、文化、岗位与个人匹配 | SKILL.md、career-and-industry.md |
| 来源读取状态、招聘时效、访谈边界 | research-protocol.md、统一证据检查器 |
| 薪资周期、金额复算与同比 | compensation-and-metrics.md、统一证据检查器 |
| 文字链／视觉链和PDF审校 | report-and-review.md |
| 撤回结论跨交付版本回流 | check_revision_consistency.py |
| 原始案例教训 | 抽象成lessons-and-tests.md，不带企业易变数字 |

## 证据格式统一

发布格式为 `schema_version: "1.0"`，采用来源 `status`、断言 `type/status`、岗位 `career_profiles`。增加原一号检查器的 `calculation` 和 `compensation.period/normalization_basis`。

不隐式接受两套同名但不同字段的输入。使用 `scripts/migrate_evidence.py --from company-v0` 或 `--from employer-v0` 显式转换，先检查输出与迁移警告。原company输入缺少来源读取状态，默认迁移为unconfirmed；不能因旧verification=matched就升级为已读事实。

输出不覆盖输入，不删除原文件。新版格式、CLI与状态语义见references/evidence-schema.md。原有本地技能目录不会因克隆此仓库被自动删除；迁移安装需自行保留备份，只启用一个调查入口，避免重复自动触发。
