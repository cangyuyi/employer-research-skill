"""All fixtures are synthetic; tests do not call the network or certify facts."""
import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from scripts.check_evidence import check, check_calculation, date_interval, main

ROOT = Path(__file__).resolve().parents[1]

def fixture():
    return json.loads((ROOT/'examples/evidence.json').read_text(encoding='utf-8'))

class EvidenceTests(unittest.TestCase):
    def codes(self, result):
        return {x['code'] for x in result['findings']}

    def test_example_passes_without_truth_claim(self):
        r=check(fixture(), (ROOT/'examples/report.md').read_text())
        self.assertTrue(r['ok']);self.assertEqual(r['warnings'],0)
        self.assertIn('no network',r['scope'])

    def test_old_schema_requires_explicit_migration(self):
        d=fixture();del d['schema_version']
        self.assertIn('schema_version',self.codes(check(d)))

    def test_duplicate_source_ids(self):
        d=fixture();d['sources'].append(copy.deepcopy(d['sources'][0]))
        self.assertIn('duplicate_id',self.codes(check(d)))

    def test_missing_source_id(self):
        d=fixture();d['claims'][0]['source_ids']=['S404']
        self.assertIn('unknown_source',self.codes(check(d)))

    def test_snippet_does_not_support_fact(self):
        d=fixture();d['sources'][0]['status']='snippet_only'
        self.assertIn('unread_support',self.codes(check(d)))

    def test_inaccessible_can_be_explicitly_unverified(self):
        d=fixture();d['sources'][0]['status']='inaccessible';d['claims'][0]['status']='unverified'
        self.assertTrue(check(d)['ok'])

    def test_supported_claim_needs_locator(self):
        d=fixture();del d['claims'][0]['locator'];del d['sources'][0]['locator']
        self.assertIn('missing_locator',self.codes(check(d)))

    def test_conflict_requires_two_read_records(self):
        d=fixture();d['claims'][0]['status']='conflicting'
        self.assertIn('insufficient_conflict_sources',self.codes(check(d)))
        other=copy.deepcopy(d['sources'][0]);other['id']='S02';d['sources'].append(other)
        d['claims'][0]['source_ids'].append('S02')
        self.assertTrue(check(d)['ok'])

    def test_analysis_not_presented_as_supported_fact(self):
        d=fixture();d['claims'][1]['status']='supported'
        self.assertIn('analysis_status_mismatch',self.codes(check(d)))

    def test_interview_cannot_be_invented_from_job_ad(self):
        d=fixture();d['claims'][0]['type']='interview_statement'
        self.assertIn('missing_interview_record',self.codes(check(d)))

    def test_interview_needs_consent_and_record_date(self):
        d=fixture();d['claims'][0]['type']='interview_statement';d['sources'][0]['kind']='interview'
        self.assertIn('missing_interview_scope',self.codes(check(d)))
        d['sources'][0].update(consent_scope='合成匿名摘要许可',recorded_at='2026-10-14')
        self.assertTrue(check(d)['ok'])
        d['sources'][0]['recorded_at']='2026-10-16'
        self.assertIn('future_interview',self.codes(check(d)))

    def test_historical_sample_not_current_vacancy(self):
        d=fixture();d['career_profiles'][0].update(current_vacancy_confirmed=True,vacancy_checked_at='2026-10-15',vacancy_evidence='合成确认')
        self.assertIn('historical_as_current',self.codes(check(d)))

    def test_current_cycle_not_automatic_confirmation(self):
        d=fixture();d['career_profiles'][0]['sample_status']='current_cycle_sample'
        self.assertTrue(check(d)['ok'])

    def test_confirmation_needs_read_evidence(self):
        d=fixture();p=d['career_profiles'][0];p.update(sample_status='current_cycle_sample',current_vacancy_confirmed=True)
        self.assertIn('vacancy_without_check',self.codes(check(d)))
        p.update(vacancy_checked_at='2026-10-15',vacancy_evidence='合成当日公开记录')
        self.assertTrue(check(d)['ok'])

    def test_future_vacancy_confirmation_rejected(self):
        d=fixture();d['career_profiles'][0].update(sample_status='current_cycle_sample',current_vacancy_confirmed=True,vacancy_checked_at='2026-10-16',vacancy_evidence='合成确认')
        self.assertIn('future_vacancy_confirmation',self.codes(check(d)))

    def test_expired_application_not_current(self):
        d=fixture();d['career_profiles'][0].update(sample_status='current_cycle_sample',current_vacancy_confirmed=True,vacancy_checked_at='2026-10-15',vacancy_evidence='合成确认',application_deadline='2026-09')
        self.assertIn('expired_as_current',self.codes(check(d)))

    def test_invalid_date_rejected(self):
        d=fixture();d['as_of']='2026-02-30'
        self.assertIn('invalid_date',self.codes(check(d)))

    def test_partial_date_precision_preserved(self):
        d=fixture();d['sources'][0]['published_at']='2026'
        before=copy.deepcopy(d);self.assertTrue(check(d)['ok']);self.assertEqual(d,before)
        lo,hi=date_interval('2024-02');self.assertEqual(hi.day,29);self.assertEqual(lo.day,1)

    def test_future_publication_is_warning_not_invented_correction(self):
        d=fixture();d['sources'][0]['published_at']='2027-01'
        self.assertIn('date_after_cutoff',self.codes(check(d)));self.assertEqual(d['sources'][0]['published_at'],'2027-01')

    def test_invalid_url_rejected(self):
        d=fixture();d['sources'][0]['location']='http://[invalid'
        self.assertIn('invalid_source_url',self.codes(check(d)))

    def test_http_success_not_identity_proof(self):
        d=fixture();d['sources'][0].update(http_status=200,page_title='另一主体采购岗')
        self.assertIn('page_identity_review',self.codes(check(d)))

    def test_unknown_pay_period_not_annualized(self):
        d=fixture();d['career_profiles'][0]['compensation'].update(period=' UNKNOWN ',normalized={'amount':'120000','period':'year'})
        self.assertIn('unknown_period_normalized',self.codes(check(d)))

    def test_known_period_normalization_needs_basis(self):
        d=fixture();c=d['career_profiles'][0]['compensation'];c['normalized']={'amount':'120000','period':'year'}
        self.assertIn('normalization_without_basis',self.codes(check(d)))
        c['normalization_basis']='合成情景：假设月固定部分乘12，非已核实待遇'
        self.assertTrue(check(d)['ok'])

    def test_missing_salary_left_unknown(self):
        d=fixture();d['career_profiles'][0]['compensation']=None
        self.assertTrue(check(d)['ok']);self.assertIn('missing_compensation',self.codes(check(d)))

    def test_wrong_scale_result_rejected(self):
        d=fixture();d['claims'][0]['calculation']['reported']='2.99'
        self.assertIn('calculation',self.codes(check(d)))

    def test_negative_and_invalid_values_rejected(self):
        for val in ['NaN','Infinity',True,{},'not-a-number']:
            with self.subTest(value=val):
                d=fixture();d['claims'][0]['calculation']['raw']=val
                self.assertIn('calculation',self.codes(check(d)))
        d=fixture();d['claims'][0]['calculation']['divisor']='-1'
        self.assertIn('calculation',self.codes(check(d)))

    def yoy(self):
        return dict(kind='yoy',current='60',baseline='100',reported='-40.00',current_year=2026,baseline_year=2025,current_period='H1',baseline_period='H1',current_scope='合成同主体',baseline_scope='合成同主体')

    def test_matching_yoy_passes(self):
        self.assertEqual(check_calculation(self.yoy()),'-40.00')

    def test_full_year_vs_half_yoy_rejected(self):
        c=self.yoy();c['baseline_period']='FY'
        with self.assertRaises(ValueError):check_calculation(c)

    def test_scope_mismatch_or_absent_yoy_rejected(self):
        c=self.yoy();c['baseline_scope']='另一主体'
        with self.assertRaises(ValueError):check_calculation(c)
        del c['baseline_scope']
        with self.assertRaises(ValueError):check_calculation(c)

    def test_yoy_year_and_nonpositive_base(self):
        for key,val in [('baseline','0'),('baseline','-100'),('baseline_year',2024),('current_year',True)]:
            c=self.yoy();c[key]=val
            with self.subTest(key=key,value=val),self.assertRaises(ValueError):check_calculation(c)

    def test_report_reference_range(self):
        self.assertIn('dangling_report_reference',self.codes(check(fixture(),'See [S01-S03]')))
        self.assertIn('invalid_citation_range',self.codes(check(fixture(),'See [S03-S01]')))

    def test_file_hash_check_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'source.txt';p.write_text('synthetic')
            d=fixture();d['sources'][0].update(local_path='source.txt',sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertTrue(check(d,base_dir=root,check_files=True)['ok'])
            p.write_text('changed')
            self.assertTrue(check(d,base_dir=root,check_files=False)['ok'])
            self.assertIn('hash_mismatch',self.codes(check(d,base_dir=root,check_files=True)))

    def test_file_scope_rejects_escape_and_external_symlink(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as other:
            root=Path(tmp);outside=Path(other)/'source.txt';outside.write_text('synthetic')
            d=fixture();d['sources'][0]['local_path']='../outside.txt'
            self.assertIn('local_file_check',self.codes(check(d,base_dir=root,check_files=True)))
            (root/'link.txt').symlink_to(outside);d['sources'][0]['local_path']='link.txt'
            self.assertIn('local_file_check',self.codes(check(d,base_dir=root,check_files=True)))

    def test_malformed_shapes_fail_cleanly(self):
        for d in [[],{}, {'schema_version':'1.0','sources':'no-list'}]:
            self.assertFalse(check(d)['ok'])
        for field,val in [('type',[]),('status',{}),('source_ids',[4])]:
            d=fixture();d['claims'][0][field]=val
            self.assertFalse(check(d)['ok'])
        d=fixture();d['sources'][0]['status']=[];self.assertFalse(check(d)['ok'])
        d=fixture();d['career_profiles'][0]['sample_status']={};self.assertFalse(check(d)['ok'])

    def test_cli_roundtrip_and_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'evidence.json';p.write_text(json.dumps(fixture()))
            before=p.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main([str(p),'--strict']),0)
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main([str(p),'--output',str(p)]),2)
            self.assertEqual(p.read_bytes(),before)
            report=root/'report.md';report.write_text('synthetic')
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main([str(p),'--report',str(report),'--output',str(report)]),2)
            self.assertEqual(report.read_text(),'synthetic')

    def test_cli_strict_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'evidence.json';d=fixture();d['career_profiles'][0]['compensation']=None;p.write_text(json.dumps(d))
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main([str(p),'--strict']),1)

if __name__=='__main__':unittest.main()
