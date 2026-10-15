# 贡献指南

1. 用合成最小样例描述失败，不提交真实履历、工资单、访谈、访问令牌或企业内部资料。
2. 修改一个判断规则时，明确输入、期望行为、错误信号与能力边界。
3. 保持单一SKILL.md入口、统一1.0格式及运行时标准库依赖；破坏格式的修改需更新迁移说明。
4. 不用固定企业数值、页数、特定字体绝对路径或某次报告的配色充当通用需求。
5. 改动后运行：

```bash
python scripts/check_project.py
python -m unittest discover -s tests -v
python scripts/check_evidence.py examples/evidence.json --report examples/report.md --strict
python scripts/check_revision_consistency.py examples/delivery-check.json
```

自动测试验证结构与已声明规则，不代表自然语言结论真实。涉及新的实际事实、网络验证或PDF渲染时，只报告真实执行范围。不要把子代理评测或外部动作写成默认获得授权。
