#!/usr/bin/env python3
"""Check declared revision rules on scoped local text; NOT truth certification.

No network, third-party packages, output writes, or PDF/DOCX extraction.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
import unicodedata


def normalize(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub("[\u2010\u2011\u2012\u2013\u2014\u2212]", "-", text)
    return re.sub(r"\s+", "", text)


def validate(data, base_dir):
    issues, artifacts, texts = [], [], {}
    root = Path(base_dir).resolve()
    reads = 0

    def error(where, message, read=False):
        nonlocal reads
        reads += int(read)
        issues.append({"location": where, "message": message})

    def nonempty(value):
        return isinstance(value, str) and bool(value.strip())

    if not isinstance(data, dict):
        error("$", "清单必须为JSON对象")
        data = {}
    rows = data.get("artifacts")
    if not isinstance(rows, list) or not rows:
        error("artifacts", "需要非空交付文本列表")
        rows = []
    seen = set()
    for i, row in enumerate(rows):
        where = f"artifacts[{i}]"
        if not isinstance(row, dict):
            error(where, "条目必须为对象")
            continue
        key, path, role = row.get("id"), row.get("path"), row.get("role", "report")
        if not all(nonempty(x) for x in [key, path, role]):
            error(where, "id、path、role需要非空字符串")
            continue
        if key in seen:
            error(where + ".id", "交付文本ID重复")
            continue
        seen.add(key)
        if type(row.get("check_citations", False)) is not bool:
            error(where + ".check_citations", "需要布尔值")
            continue
        try:
            target = (root / path).resolve()
            if Path(path).is_absolute() or not target.is_relative_to(root):
                raise ValueError("只读取清单目录内的相对路径，不允许越界或外部符号链接")
            if target.suffix.lower() not in {".md", ".txt", ".csv"}:
                raise ValueError("只支持UTF-8的md/txt/csv；二进制文档先实际提取文本")
            text = target.read_text(encoding="utf-8-sig")
        except (OSError, ValueError, UnicodeError, RuntimeError) as exc:
            error(where + ".path", str(exc), True)
            continue
        artifacts.append({**row, "role": role, "where": where})
        texts[key] = text

    source_ids = data.get("source_ids", [])
    if not isinstance(source_ids, list) or not all(nonempty(x) for x in source_ids):
        error("source_ids", "需要来源ID字符串列表")
        source_ids = []
    if len(source_ids) != len(set(source_ids)):
        error("source_ids", "来源ID重复")
    known = set(source_ids)
    for item in artifacts:
        if not item.get("check_citations", False):
            continue
        if not known:
            error(item["where"] + ".check_citations", "启用引用检查需提供source_ids")
            continue
        for m in re.finditer(r"\[S(\d{2,4})(?:\s*[-—–]\s*S(\d{2,4}))?\]", texts[item["id"]]):
            start, end = int(m[1]), int(m[2] or m[1])
            if end < start or end-start > 200:
                error(item["where"], "引用范围无效：" + m[0])
                continue
            width = len(m[1])
            for n in range(start, end + 1):
                ref = "S" + str(n).zfill(width)
                if ref not in known:
                    error(item["where"], "未登记来源ID：" + ref)

    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        error("rules", "需要至少一项当前任务的检查规则")
        rules = []
    rule_ids, evaluations = set(), 0
    for i, rule in enumerate(rules):
        where = f"rules[{i}]"
        if not isinstance(rule, dict):
            error(where, "规则必须是对象")
            continue
        key, kind, text = rule.get("id"), rule.get("type"), rule.get("text")
        if not nonempty(key) or not nonempty(text) or kind not in ["must_contain", "must_not_contain"]:
            error(where, "规则需id、text及must_contain/must_not_contain类型")
            continue
        if key in rule_ids:
            error(where + ".id", "规则ID重复")
            continue
        rule_ids.add(key)
        roles = rule.get("roles", ["report"])
        if not isinstance(roles, list) or not roles or not all(nonempty(x) for x in roles):
            error(where + ".roles", "需要非空角色字符串列表")
            continue
        selected = [a for a in artifacts if a["role"] in roles]
        if not selected:
            error(where, "规则未匹配任何可读取的交付文本，不作通过处理")
            continue
        needle = normalize(text)
        if not needle:
            error(where + ".text", "规范化后不得为空")
            continue
        for item in selected:
            found = needle in normalize(texts[item["id"]])
            evaluations += 1
            if (kind == "must_contain" and not found) or (kind == "must_not_contain" and found):
                error(where, f"{item['id']}不满足{kind}：{text}")
    return {"status": "declared_checks_passed" if not issues else "needs_review", "scope": "declared_text_rules_only_not_semantic_or_factual_verification", "artifacts_read": len(artifacts), "rule_evaluations": evaluations, "errors": len(issues), "read_errors": reads, "issues": issues}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        result = validate(data, args.manifest.parent)
    except (OSError, ValueError) as exc:
        print("无法读取检查清单：" + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["read_errors"] else 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
