#!/usr/bin/env python3
"""Offline checks of declared evidence, scope and arithmetic; NOT truth certification."""
from __future__ import annotations
import argparse
import calendar
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

SOURCE_STATUSES = {'read', 'snippet_only', 'inaccessible', 'excluded', 'unconfirmed'}
CLAIM_TYPES = {'public_record', 'company_statement', 'interview_statement', 'analysis', 'recommendation'}
CLAIM_STATUSES = {'supported', 'conflicting', 'historical', 'unverified', 'analysis'}
SAMPLE_STATUSES = {'current_cycle_sample', 'historical_sample', 'industry_reference', 'unknown'}
PERIODS = {'hour', 'day', 'week', 'month', 'quarter', 'year', 'task', 'unknown'}


def text(value):
    return isinstance(value, str) and bool(value.strip())


def date_interval(value):
    """Preserve partial-date precision instead of silently inventing a day."""
    if not isinstance(value, str):
        raise ValueError('日期必须是ISO字符串')
    if re.fullmatch(r'\d{4}', value):
        y = int(value)
        return date(y, 1, 1), date(y, 12, 31)
    if re.fullmatch(r'\d{4}-\d{2}', value):
        y, m = map(int, value.split('-'))
        return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('需要YYYY、YYYY-MM或YYYY-MM-DD')
    d = date.fromisoformat(value)
    return d, d


def decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('需要十进制数值，推荐字符串')
    result = Decimal(str(value).replace(',', ''))
    if not result.is_finite():
        raise ValueError('不接受NaN或无穷大')
    return result


def check_calculation(calc):
    if not isinstance(calc, dict):
        raise ValueError('calculation必须为对象')
    places = calc.get('decimals', 2)
    if type(places) is not int or not 0 <= places <= 12:
        raise ValueError('decimals必须为0至12的整数')
    with localcontext() as ctx:
        ctx.prec = 60
        kind = calc.get('kind')
        if kind == 'scale':
            divisor = decimal(calc['divisor'])
            if divisor <= 0:
                raise ValueError('单位换算除数必须大于零')
            result = decimal(calc['raw']) / divisor
        elif kind == 'yoy':
            cp, bp = calc.get('current_period'), calc.get('baseline_period')
            if not text(cp) or cp != bp:
                raise ValueError('同比期间不一致；全年不能与半年直接同比')
            cy, by = calc.get('current_year'), calc.get('baseline_year')
            if type(cy) is not int or type(by) is not int or cy != by + 1:
                raise ValueError('同比年份应相隔一年')
            if any(not text(calc.get(k)) for k in ['current_scope', 'baseline_scope']):
                raise ValueError('同比需显式声明current_scope与baseline_scope')
            if calc['current_scope'] != calc['baseline_scope']:
                raise ValueError('同比主体或统计范围声明不同')
            base = decimal(calc['baseline'])
            if base <= 0:
                raise ValueError('基期非正，需另行解释，不自动套通常同比')
            result = (decimal(calc['current']) / base - 1) * 100
        else:
            raise ValueError('算式仅支持scale或yoy')
        actual = result.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        if actual != decimal(calc['reported']):
            raise ValueError(f'复算为{actual}，与reported不一致')
        return str(actual)


def check(data, report_text=None, base_dir=None, check_files=False):
    findings = []
    counts = {'sources': 0, 'claims': 0, 'career_profiles': 0, 'calculations': 0}
    root = Path(base_dir or '.').resolve()

    def add(level, code, message, item=''):
        findings.append({'level': level, 'code': code, 'item': item, 'message': message})

    def finish():
        errors = sum(x['level'] == 'error' for x in findings)
        return {'ok': errors == 0, 'errors': errors,
                'warnings': sum(x['level'] == 'warning' for x in findings),
                'counts': counts, 'scope': 'Declared structure, references and arithmetic only; no network, semantic truth, actual vacancy or payroll verification.',
                'findings': findings}

    def parse(value, field, item, required=False, precise=False):
        if value is None or value == '':
            if required:
                add('error', 'missing_date', field + '需要日期', item)
            return None
        try:
            result = date_interval(value)
            if precise and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError(field + '需明确到日')
            return result
        except (ValueError, TypeError, OverflowError) as exc:
            add('error', 'invalid_date', field + ': ' + str(exc), item)
            return None

    if not isinstance(data, dict):
        add('error', 'invalid_root', '输入必须为JSON对象')
        return finish()
    if data.get('schema_version') != '1.0':
        add('error', 'schema_version', '需显式schema_version=1.0；旧格式请先迁移')
    cutoff = parse(data.get('as_of'), 'as_of', 'root', True, True)
    cutoff = cutoff[0] if cutoff else None

    def index(field, required=False):
        rows = data.get(field, [])
        if not isinstance(rows, list):
            add('error', 'invalid_list', field + '需为列表', field)
            return {}
        result = {}
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                add('error', 'invalid_record', '条目需为对象', f'{field}[{i}]')
                continue
            key = row.get('id')
            if not text(key) or re.search(r'\s', key):
                add('error', 'invalid_id', 'ID需为非空且无空白字符串', f'{field}[{i}]')
                continue
            if key in result:
                add('error', 'duplicate_id', 'ID重复', key)
            else:
                result[key] = row
        if required and not result:
            add('error', 'empty_collection', field + '不能为空', field)
        counts[field] = len(result)
        return result

    sources = index('sources', True)
    claims = index('claims', True)
    profiles = index('career_profiles')
    used = set()
    for sid, source in sources.items():
        for field in ['title', 'publisher', 'location']:
            if not text(source.get(field)):
                add('error', 'missing_source_field', field + '需要非空字符串', sid)
        status = source.get('status')
        if not isinstance(status, str) or status not in SOURCE_STATUSES:
            add('error', 'invalid_source_status', '来源status未知', sid)
        location = source.get('location')
        if text(location) and '://' in location:
            try:
                url = urlsplit(location)
                if url.scheme not in {'http', 'https'} or not url.netloc:
                    raise ValueError('不是有效http(s)来源地址')
            except ValueError as exc:
                add('error', 'invalid_source_url', str(exc), sid)
        for field in ['published_at', 'data_as_of', 'accessed_at']:
            value = parse(source.get(field), field, sid, field == 'accessed_at', field == 'accessed_at')
            if cutoff and value and value[0] > cutoff:
                add('warning', 'date_after_cutoff', field + '晚于调查截止日；需复核版本', sid)
        page_title = source.get('page_title')
        if page_title and text(source.get('title')) and source['title'] not in str(page_title):
            add('warning', 'page_identity_review', '页面标题不完全匹配，需核对主体，不能只看HTTP', sid)
        digest = source.get('sha256')
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch('[a-fA-F0-9]{64}', digest)):
            add('error', 'invalid_hash', 'sha256格式错误', sid)
        if check_files and source.get('local_path') is not None:
            try:
                rel = source['local_path']
                if not text(rel) or Path(rel).is_absolute():
                    raise ValueError('local_path需为证据目录内相对路径')
                path = (root / rel).resolve()
                if not path.is_relative_to(root):
                    raise ValueError('拒绝目录越界或指向外部的符号链接')
                if not path.is_file():
                    raise ValueError('存档文件不存在')
                if digest and isinstance(digest, str):
                    h = hashlib.sha256()
                    with path.open('rb') as stream:
                        for block in iter(lambda: stream.read(65536), b''):
                            h.update(block)
                    if h.hexdigest() != digest.lower():
                        add('error', 'hash_mismatch', '存档哈希不同；不等于已证明内容虚假', sid)
            except (OSError, ValueError, RuntimeError) as exc:
                add('error', 'local_file_check', str(exc), sid)
        elif check_files and digest:
            add('warning', 'hash_not_checked', '未提供local_path，未比对哈希', sid)

    def references(row, item, required=False):
        ids = row.get('source_ids', [])
        if not isinstance(ids, list) or not all(text(x) for x in ids):
            add('error', 'invalid_source_ids', 'source_ids需为字符串列表', item)
            return []
        if required and not ids:
            add('error', 'missing_support', '缺少支撑来源', item)
        if len(ids) != len(set(ids)):
            add('warning', 'duplicate_reference', '重复来源ID', item)
        resolved = []
        for sid in dict.fromkeys(ids):
            if sid not in sources:
                add('error', 'unknown_source', '未登记来源：' + sid, item)
            else:
                used.add(sid)
                resolved.append(sources[sid])
        return resolved

    for cid, claim in claims.items():
        if not text(claim.get('text')):
            add('error', 'missing_claim_text', '断言需要正文', cid)
        kind, status = claim.get('type'), claim.get('status')
        if not isinstance(kind, str) or kind not in CLAIM_TYPES:
            add('error', 'invalid_claim_type', '断言type未知', cid)
        if not isinstance(status, str) or status not in CLAIM_STATUSES:
            add('error', 'invalid_claim_status', '断言status未知', cid)
        analysis = kind in ['analysis', 'recommendation']
        resolved = references(claim, cid, not analysis and status != 'unverified')
        read = [x for x in resolved if x.get('status') == 'read']
        factual = status in ['supported', 'historical', 'conflicting']
        if not analysis and factual and not read:
            add('error', 'unread_support', '已支持事实不能只靠摘要、失败或未确认来源', cid)
        if status == 'conflicting' and len(read) < 2:
            add('error', 'insufficient_conflict_sources', '来源冲突至少需要两份已读记录', cid)
        if analysis != (status == 'analysis'):
            add('warning', 'analysis_status_mismatch', '分析／建议应与事实状态分开', cid)
        if factual and not text(claim.get('locator')) and not any(text(x.get('locator')) for x in read):
            add('error', 'missing_locator', '已支持事实需有原文定位', cid)
        if kind == 'interview_statement':
            interviews = [x for x in read if x.get('kind') == 'interview']
            if not interviews:
                add('error', 'missing_interview_record', '访谈断言需有实际已读访谈记录', cid)
            for source in interviews:
                if not text(source.get('consent_scope')):
                    add('error', 'missing_interview_scope', '访谈需约定引用／匿名范围', source['id'])
                recorded = parse(source.get('recorded_at'), 'recorded_at', source['id'], True, True)
                if cutoff and recorded and recorded[0] > cutoff:
                    add('error', 'future_interview', '访谈记录晚于调查截止日', source['id'])
        if 'calculation' in claim:
            counts['calculations'] += 1
            try:
                check_calculation(claim['calculation'])
            except (InvalidOperation, ValueError, TypeError, KeyError, OverflowError) as exc:
                add('error', 'calculation', str(exc), cid)

    for jid, profile in profiles.items():
        if not text(profile.get('title')):
            add('error', 'missing_job_title', '岗位需原始名称', jid)
        resolved = references(profile, jid, True)
        sample = profile.get('sample_status')
        if not isinstance(sample, str) or sample not in SAMPLE_STATUSES:
            add('error', 'invalid_sample_status', 'sample_status未知', jid)
        confirmed = profile.get('current_vacancy_confirmed', False)
        if not isinstance(confirmed, bool):
            add('error', 'invalid_vacancy_flag', 'current_vacancy_confirmed需为布尔值', jid)
        if confirmed is True:
            if sample == 'historical_sample':
                add('error', 'historical_as_current', '历史样本与新确认空缺须分别记录', jid)
            if not text(profile.get('vacancy_evidence')):
                add('error', 'vacancy_without_check', '确认空缺需有核实说明', jid)
            checked = parse(profile.get('vacancy_checked_at'), 'vacancy_checked_at', jid, True, True)
            if cutoff and checked and checked[0] > cutoff:
                add('error', 'future_vacancy_confirmation', '不能用截止日后的确认冒充当时已知', jid)
            if not any(x.get('status') == 'read' for x in resolved):
                add('error', 'vacancy_without_read_source', '确认空缺需实际已读支持', jid)
            deadline = parse(profile.get('application_deadline'), 'application_deadline', jid)
            if cutoff and deadline and deadline[1] < cutoff:
                add('error', 'expired_as_current', '截止期限已过，不能称当期空缺已确认', jid)
        if not any(x.get('status') == 'read' for x in resolved):
            add('warning', 'profile_not_verified', '岗位缺少已读支持，仅作明确标注的线索', jid)
        comp = profile.get('compensation')
        if comp is None:
            add('warning', 'missing_compensation', '未取得可靠薪资，不从别岗补齐', jid)
            continue
        if not isinstance(comp, dict):
            add('error', 'invalid_compensation', 'compensation需为对象或null', jid)
            continue
        if not text(comp.get('raw')):
            add('error', 'missing_raw_compensation', '保留原始薪资字段', jid)
        period = comp.get('period')
        period = period.strip().lower() if isinstance(period, str) else ''
        if period not in PERIODS:
            add('error', 'invalid_pay_period', '未知周期写unknown，不能补月薪', jid)
        normalized = comp.get('normalized')
        if period == 'unknown':
            if normalized is not None:
                add('error', 'unknown_period_normalized', '未知计薪周期不能标准化为月薪／年薪', jid)
            add('warning', 'unknown_pay_period', '计薪周期未确认，保持限定', jid)
        elif normalized is not None:
            if not isinstance(normalized, dict) or not normalized:
                add('error', 'invalid_normalized_pay', 'normalized需为非空对象或null', jid)
            if not text(comp.get('normalization_basis')):
                add('error', 'normalization_without_basis', '换算需说明依据及假设，不代表实际待遇', jid)

    if report_text is not None:
        if not isinstance(report_text, str):
            add('error', 'invalid_report_text', '报告提取文本需为字符串')
        else:
            cited = set()
            for m in re.finditer(r'\[S(\d{2,4})(?:\s*[-—–]\s*S(\d{2,4}))?\]', report_text):
                start, end = int(m[1]), int(m[2] or m[1])
                if end < start or end - start > 200:
                    add('error', 'invalid_citation_range', '引用范围无效：' + m[0])
                    continue
                cited.update('S' + str(i).zfill(len(m[1])) for i in range(start, end + 1))
            for sid in sorted(cited - sources.keys()):
                add('error', 'dangling_report_reference', '报告引用未登记来源', sid)
            for sid in sorted(cited & sources.keys()):
                if sources[sid].get('status') != 'read':
                    add('warning', 'report_cites_unread', '需明确引用的只是线索或访问限制', sid)
            used |= cited & sources.keys()
    for sid in sorted(sources.keys() - used):
        if not text(sources[sid].get('background_purpose')):
            add('warning', 'unused_source', '无支撑作用的来源需删除或说明背景用途', sid)
    return finish()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--report', type=Path, help='实际Markdown或PDF/Word提取文本，不直接读取二进制')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-files', action='store_true', help='显式读取证据目录内存档，核对可选哈希')
    parser.add_argument('--strict', action='store_true', help='警告也使退出码非零')
    parser.add_argument('--json', action='store_true', help='兼容参数；默认已输出JSON')
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.evidence.read_text(encoding='utf-8-sig'))
        report = args.report.read_text(encoding='utf-8-sig') if args.report else None
        protected = [args.evidence] + ([args.report] if args.report else [])
        if isinstance(data, dict) and isinstance(data.get('sources'), list):
            for source in data['sources']:
                if isinstance(source, dict) and text(source.get('local_path')):
                    protected.append(args.evidence.parent / source['local_path'])
        if args.output and args.output.resolve() in [x.resolve() for x in protected]:
            raise ValueError('输出不能覆盖输入、报告或原始存档')
        result = check(data, report, args.evidence.parent, args.check_files)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding='utf-8')
        else:
            print(rendered, end='')
        return 1 if result['errors'] or (args.strict and result['warnings']) else 0
    except (OSError, ValueError) as exc:
        print('检查失败：' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
