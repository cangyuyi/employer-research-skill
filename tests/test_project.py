from pathlib import Path
import tempfile
import unittest
from scripts.check_project import check_project, ROOT, REQUIRED

class ProjectTests(unittest.TestCase):
    def make_root(self, path):
        for rel in REQUIRED:
            p=path/rel;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text('{}' if p.suffix=='.json' else 'synthetic',encoding='utf-8')
        (path/'SKILL.md').write_text('---\nname: company-job-investigation\ndescription: synthetic test\n---\n# Test\n',encoding='utf-8')

    def test_real_project_has_valid_local_links(self):
        self.assertTrue(check_project(ROOT)['ok'])

    def test_missing_required_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(check_project(tmp)['ok'])

    def test_selected_token_pattern_detected_without_leaking_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_root(root)
            (root/'note.md').write_text('gh'+'p_'+'a'*36)
            r=check_project(root)
            self.assertFalse(r['ok']);self.assertTrue(any('Potential access token' in x for x in r['issues']))
            self.assertFalse(any('a'*36 in x for x in r['issues']))

    def test_broken_local_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_root(root)
            (root/'README.md').write_text('[link](missing.md)')
            self.assertFalse(check_project(root)['ok'])

    def test_external_symlink_not_read(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as other:
            root=Path(tmp);self.make_root(root);target=Path(other)/'outside.md';target.write_text('synthetic')
            (root/'outside.md').symlink_to(target)
            self.assertTrue(any('External symlink' in x for x in check_project(root)['issues']))

if __name__=='__main__':unittest.main()
