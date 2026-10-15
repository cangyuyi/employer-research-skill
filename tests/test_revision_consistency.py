"""Synthetic offline regression cases; no real employer facts or network."""
import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from scripts.check_revision_consistency import validate, main


class RevisionChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.root/'report.md').write_text('合成正文：未经审计。[S01]',encoding='utf-8')
        (self.root/'pdf.txt').write_text('合成PDF实际提取文本：未经审计。',encoding='utf-8')
        (self.root/'audit.md').write_text('问题追溯：已撤回合成补贴900-1200元。',encoding='utf-8')
        self.data = {
            'artifacts': [
                {'id':'main','path':'report.md','role':'report','check_citations':True},
                {'id':'pdf','path':'pdf.txt','role':'report'},
                {'id':'audit','path':'audit.md','role':'audit'}],
            'source_ids':['S01'],
            'rules':[
                {'id':'withdrawal','type':'must_not_contain','text':'合成补贴900-1200元'},
                {'id':'qualification','type':'must_contain','text':'未经审计'}]}

    def test_clean_bundle_allows_audit_trace(self):
        r=validate(self.data,self.root)
        self.assertEqual(r['errors'],0);self.assertEqual(r['rule_evaluations'],4)

    def test_withdrawn_conclusion_in_pdf_is_caught(self):
        (self.root/'pdf.txt').write_text('未经审计；合成补贴900-1200元',encoding='utf-8')
        self.assertGreater(validate(self.data,self.root)['errors'],0)

    def test_normalization_catches_spaced_unicode_range(self):
        (self.root/'pdf.txt').write_text('未经审计；合成补贴 ９００ — １２００元',encoding='utf-8')
        self.assertGreater(validate(self.data,self.root)['errors'],0)

    def test_required_note_missing_in_one_artifact(self):
        (self.root/'pdf.txt').write_text('合成正文缺少限定条件',encoding='utf-8')
        self.assertGreater(validate(self.data,self.root)['errors'],0)

    def test_unregistered_citation_is_caught(self):
        (self.root/'report.md').write_text('未经审计。[S01-S03]',encoding='utf-8')
        self.assertGreater(validate(self.data,self.root)['errors'],0)
        self.data['source_ids']=['S01','S02','S03']
        self.assertEqual(validate(self.data,self.root)['errors'],0)

    def test_no_matching_role_is_not_vacuous_success(self):
        self.data['rules'][0]['roles']=['absent-role']
        self.assertGreater(validate(self.data,self.root)['errors'],0)

    def test_duplicate_artifacts_are_rejected(self):
        self.data['artifacts'].append(copy.deepcopy(self.data['artifacts'][0]))
        self.assertGreater(validate(self.data,self.root)['errors'],0)

    def test_missing_text_is_read_error(self):
        self.data['artifacts'][0]['path']='missing.md'
        self.assertGreater(validate(self.data,self.root)['read_errors'],0)

    def test_binary_input_is_rejected(self):
        self.data['artifacts'][0]['path']='report.pdf'
        self.assertGreater(validate(self.data,self.root)['read_errors'],0)

    def test_external_path_and_symlink_are_rejected(self):
        self.data['artifacts'][0]['path']='../outside.md'
        self.assertGreater(validate(self.data,self.root)['read_errors'],0)
        with tempfile.TemporaryDirectory() as other:
            target=Path(other)/'private.txt';target.write_text('未经审计')
            (self.root/'link.txt').symlink_to(target)
            self.data['artifacts'][0]['path']='link.txt'
            self.assertGreater(validate(self.data,self.root)['read_errors'],0)

    def test_bad_shapes_do_not_crash(self):
        for data in [[],{}, {'artifacts':[1], 'rules':[None]}, {'artifacts':[], 'source_ids':[{}]}]:
            self.assertGreater(validate(data,self.root)['errors'],0)
        data=copy.deepcopy(self.data);data['rules'][0]['type']=[]
        self.assertGreater(validate(data,self.root)['errors'],0)

    def test_cli_is_read_only(self):
        p=self.root/'manifest.json';p.write_text(json.dumps(self.data),encoding='utf-8')
        before={f.name:f.read_bytes() for f in self.root.iterdir() if f.is_file()}
        with contextlib.redirect_stdout(io.StringIO()):code=main([str(p)])
        self.assertEqual(code,0)
        self.assertEqual(before,{f.name:f.read_bytes() for f in self.root.iterdir() if f.is_file()})


if __name__=='__main__':
    unittest.main()
