import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from scripts.migrate_evidence import migrate, main
from scripts.check_evidence import check

ROOT=Path(__file__).resolve().parents[1]

class MigrationTests(unittest.TestCase):
    def old_company(self):
        return {'as_of':'2026-10-15','sources':[{'id':'S01','title':'合成旧资料','publisher':'合成机构','url':'https://example.invalid/legacy','retrieved_at':'2026-10-15','published_at':None}], 'claims':[{'id':'C01','text':'合成旧断言','kind':'fact','verification':'matched','source_ids':['S01'],'locator':'合成行'}],'jobs':[{'id':'J01','title':'合成旧岗位','source_ids':['S01'],'salary':{'raw':'合成金额20000元以上','period':'unknown','normalized':None}}]}

    def test_missing_read_state_not_promoted(self):
        out=migrate(self.old_company(),'company-v0')
        self.assertEqual(out['sources'][0]['status'],'unconfirmed')
        self.assertEqual(out['claims'][0]['status'],'unverified')
        self.assertTrue(out['migration']['warnings']);self.assertTrue(check(out)['ok'])

    def test_migration_does_not_mutate_input(self):
        data=self.old_company();before=json.dumps(data,sort_keys=True)
        migrate(data,'company-v0');self.assertEqual(json.dumps(data,sort_keys=True),before)

    def test_employer_format_preserves_read_records(self):
        data=json.loads((ROOT/'examples/evidence.json').read_text());del data['schema_version']
        out=migrate(data,'employer-v0')
        self.assertEqual(out['claims'][0]['status'],'supported');self.assertTrue(check(out)['ok'])

    def test_salary_period_not_invented(self):
        out=migrate(self.old_company(),'company-v0')
        self.assertEqual(out['career_profiles'][0]['compensation']['period'],'unknown')
        self.assertFalse(out['career_profiles'][0]['current_vacancy_confirmed'])

    def test_invalid_input_rejected(self):
        for data in [[],{'sources':'not-list'}, {'sources':[2],'claims':[]}]:
            with self.assertRaises(ValueError):migrate(data,'company-v0')

    def test_malformed_legacy_claim_fails_cleanly(self):
        d=self.old_company();d['claims'][0]['kind']=[]
        with self.assertRaises(ValueError):migrate(d,'company-v0')

    def test_cli_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'old.json';p.write_text(json.dumps(self.old_company()));before=p.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main([str(p),'--from','company-v0','--output',str(p)]),2)
            self.assertEqual(p.read_bytes(),before)
            new=Path(tmp)/'new.json';self.assertEqual(main([str(p),'--from','company-v0','--output',str(new)]),0)
            self.assertEqual(json.loads(new.read_text())['schema_version'],'1.0')

if __name__=='__main__':unittest.main()
