#!/usr/bin/env python3
"""Explicit legacy-format migration; never promotes missing read evidence to truth."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import sys


def migrate(data, source_format):
    if not isinstance(data, dict) or source_format not in ['company-v0', 'employer-v0']:
        raise ValueError('需提供对象及明确的旧格式名称')
    warnings = []
    sources = data.get('sources', [])
    claims = data.get('claims', [])
    if not isinstance(sources, list) or not isinstance(claims, list):
        raise ValueError('旧sources与claims必须为列表')
    out = {'schema_version': '1.0', 'as_of': data.get('as_of'), 'sources': [], 'claims': [], 'career_profiles': []}
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError('旧来源条目必须为对象')
        s = copy.deepcopy(source)
        if source_format == 'company-v0':
            s['location'] = s.pop('url', None) or s.get('local_path', '')
            s['accessed_at'] = s.pop('retrieved_at', None)
        if not s.get('publisher'):
            s['publisher'] = '未记录（旧格式）'
            warnings.append(str(s.get('id')) + ': 发布者未记录，须人工补核')
        if s.get('status') not in ['read', 'snippet_only', 'inaccessible', 'excluded', 'unconfirmed']:
            s['status'] = 'unconfirmed'
            warnings.append(str(s.get('id')) + ': 旧格式无已读状态，保留unconfirmed')
        out['sources'].append(s)
    known = {s.get('id'): s for s in out['sources'] if isinstance(s.get('id'), str)}
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError('旧断言条目必须为对象')
        c = copy.deepcopy(claim)
        if source_format == 'company-v0':
            kind = c.pop('kind', None)
            verification = c.pop('verification', None)
            if not isinstance(kind, str) or (verification is not None and not isinstance(verification, str)):
                raise ValueError('旧kind与verification类型不正确')
            c['type'] = {'fact': 'public_record', 'analysis': 'analysis', 'recommendation': 'recommendation'}.get(kind, kind)
            c['status'] = 'analysis' if kind in ['analysis', 'recommendation'] else {'matched': 'supported', 'conflict': 'conflicting'}.get(verification, 'unverified')
            c['legacy_verification'] = verification
        refs = c.get('source_ids', [])
        read = [known.get(s) for s in refs if isinstance(s, str) and known.get(s, {}).get('status') == 'read'] if isinstance(refs, list) else []
        if c.get('type') not in ['analysis', 'recommendation'] and c.get('status') in ['supported', 'historical', 'conflicting'] and not read:
            c['status'] = 'unverified'
            warnings.append(str(c.get('id')) + ': 缺少已读支持，不迁移成已支持事实')
        calc = c.get('calculation')
        if isinstance(calc, dict) and calc.get('kind') == 'yoy' and not all(calc.get(k) for k in ['current_scope', 'baseline_scope']):
            warnings.append(str(c.get('id')) + ': 同比缺主体范围声明，须补核后才能通过检查')
        out['claims'].append(c)
    profiles = data.get('jobs' if source_format == 'company-v0' else 'career_profiles', [])
    if not isinstance(profiles, list):
        raise ValueError('旧岗位集合必须为列表')
    for profile in profiles:
        if not isinstance(profile, dict):
            raise ValueError('旧岗位条目必须为对象')
        p = copy.deepcopy(profile)
        if source_format == 'company-v0':
            p['compensation'] = p.pop('salary', None)
            p.setdefault('sample_status', 'unknown')
        p.setdefault('current_vacancy_confirmed', False)
        out['career_profiles'].append(p)
    out['migration'] = {'from': source_format, 'warnings': warnings, 'notice': '字段转换不是事实重新核验；请检查输出和所有未知项。'}
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--from', dest='source_format', choices=['company-v0', 'employer-v0'], required=True)
    p.add_argument('--output', type=Path)
    args = p.parse_args(argv)
    try:
        data = json.loads(args.input.read_text(encoding='utf-8-sig'))
        result = migrate(data, args.source_format)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            if args.output.resolve() == args.input.resolve() or args.output.exists():
                raise ValueError('输出须为新路径，不覆盖原稿或已有文件')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding='utf-8')
        else:
            print(rendered, end='')
        return 0
    except (OSError, ValueError) as exc:
        print('迁移失败：' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
