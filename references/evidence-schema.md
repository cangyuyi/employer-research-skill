# 统一证据格式 1.0

只有一种发布格式。两个旧技能的同名脚本输入不兼容，因此新版不默默猜格式；先运行显式迁移，详见[迁移说明](../docs/merge-notes.md)。

## 根字段

`schema_version: "1.0"`、精确到日的`as_of`、非空`sources`和`claims`；`career_profiles`可选。规范参照[JSON Schema](../schemas/evidence.schema.json)，脚本实施文档中描述的关键规则，不宣称覆盖JSON Schema的所有约束。

## 来源 sources

- 必填：`id / title / publisher / location / accessed_at / status`。location是实际取得的URL或原始本地材料位置，不能猜ID。
- `status`：`read / snippet_only / inaccessible / excluded / unconfirmed`。read表示实际读到目标正文，不代表独立认证。
- `published_at / data_as_of`：可null或YYYY、YYYY-MM、YYYY-MM-DD；未知不补精确日。`accessed_at`必须精确到日。
- 可选：`kind / scope / original_filename / locator / page_title / limitations / background_purpose`。
- 需检查存档时提供`local_path`（证据JSON目录内相对路径）、可选`sha256`；只有`--check-files`才读取这些文件，拒绝目录越界及外部符号链接。
- 访谈来源另有`kind: interview / recorded_at / consent_scope`；采访方式、允许引用范围由真实授权决定，不由字段自动生成。

## 断言 claims

- 必填：`id / text / type / status / source_ids`。
- `type`：`public_record / company_statement / interview_statement / analysis / recommendation`。
- `status`：`supported / historical / conflicting / unverified / analysis`。
- 已支持／历史事实需至少一份read来源及断言或来源层的`locator`；冲突需至少两份read记录，但脚本不判断独立性或实际冲突。
- 分析和建议使用analysis状态，允许来源为空；未核实事实不能借该类型伪装为已知。
- 可有`qualifiers / remaining_questions / calculation`。金额计算与原文匹配是两个核验步骤。

### 算式

`scale`包含`raw / divisor / reported / decimals`；数值推荐十进制字符串，使用Decimal四舍五入。

`yoy`包含`current / baseline / reported / current_year / baseline_year / current_period / baseline_period / current_scope / baseline_scope`，另可有decimals。期间标签、主体／统计范围声明应一致，年份相隔一年且基期为正才能自动计算。字段一致只说明作者如此声明，不证明实际可比。

## 岗位 career_profiles

- 必填：`id / title / source_ids / sample_status`；样本状态为`current_cycle_sample / historical_sample / industry_reference / unknown`。
- `current_vacancy_confirmed`默认false。当届样本不等于实时空缺；true必须有`vacancy_checked_at / vacancy_evidence`与read支持，不能晚于调查截止日，也不能与historical_sample或已过报名期限并存。
- `application_deadline`可保留日期精度，历史与当前确认分别建记录。
- `relevance / qualifications / tasks / working_conditions`按任务补充；事实字段与研究归类分别说明。
- `compensation`可null；对象至少有`raw / period`。period为`hour / day / week / month / quarter / year / task / unknown`。
- 周期unknown时normalized只能null；已知周期进行标准化时另附`normalization_basis`，明确假设及是否仅为分析。币种、税前税后和浮动成分不设默认事实。

## CLI与退出码

```bash
python scripts/check_evidence.py examples/evidence.json --report examples/report.md
python scripts/check_evidence.py examples/evidence.json --check-files --strict
python scripts/migrate_evidence.py old.json --from company-v0 --output migrated.json
```

默认JSON输出；`--output`只写显式指定路径，不覆盖证据输入、报告或原始存档。退出码0：已声明规则通过；1：错误或strict下有警告；2：输入、读取或执行失败。脚本不联网、不安装，不改变状态为read，不认证事实。

## 交付版本检查

`check_revision_consistency.py`读取本地UTF-8的md/txt/csv，不直接解析PDF或Word。先实际提取最终文件文字，再写清单。

- `artifacts`：`id / path / role`，相对路径限清单目录内；`role`默认report，追溯文件可用audit。
- `rules`：`id / type / text`；type为must_contain或must_not_contain；roles默认只检查report。
- 规则按Unicode规范化、常见横线统一和空白折叠匹配，不识别所有同义改写。未匹配任何交付文件不作通过。
- `source_ids`与artifact的`check_citations: true`可检查方括号S编号；不验证来源是否充分支撑断言。
- 只向标准输出写结果，不改文件。退出码0为声明规则通过、1发现问题、2读取或输入失败。

不要把原始文字稿复制成“PDF提取文本”充数。审校记录可保留旧结论，正文不得残留已撤回断言。参见[合成清单](../examples/delivery-check.json)。
