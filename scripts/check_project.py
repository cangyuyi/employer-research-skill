#!/usr/bin/env python3
"""Lightweight offline project/link/privacy checks; not a comprehensive security audit."""
from pathlib import Path
import ast
import json
import re
import sys
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
REQUIRED=['SKILL.md','agents/openai.yaml','README.md','LICENSE','VERSION','schemas/evidence.schema.json','examples/evidence.json','references/evidence-schema.md']
SKIP={'.git','__pycache__','.venv','venv','.cache'}

def check_project(root=ROOT):
    root=Path(root).resolve();issues=[]
    for rel in REQUIRED:
        if not (root/rel).is_file():issues.append('Missing '+rel)
    skill=(root/'SKILL.md').read_text(encoding='utf-8') if (root/'SKILL.md').exists() else ''
    front=re.match(r'^---\n(.*?)\n---\n',skill,re.S)
    if not front:issues.append('Missing skill frontmatter')
    else:
        for key in ['name','description']:
            if not re.search(r'^'+key+r':\s*\S',front[1],re.M):issues.append('Missing '+key)
        if not re.search(r'^name: company-job-investigation$',front[1],re.M):issues.append('Unexpected canonical skill name')
    scans=0
    for path in root.rglob('*'):
        if not path.is_file() or any(part in SKIP for part in path.relative_to(root).parts):continue
        rel=str(path.relative_to(root));scans+=1
        if not path.resolve().is_relative_to(root):
            issues.append('External symlink not read '+rel);continue
        if path.name in {'.env','id_rsa','id_ed25519'} or path.suffix in {'.pem','.key'}:issues.append('Potential secret file '+rel)
        if path.suffix not in {'.md','.py','.json','.yaml','.yml','.txt'} and path.name not in {'README','LICENSE'}:continue
        try:body=path.read_text(encoding='utf-8')
        except UnicodeError:issues.append('Unexpected binary '+rel);continue
        if re.search(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b',body):issues.append('Potential access token '+rel)
        if re.search(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',body):issues.append('Potential private key '+rel)
        home_pattern=r'/'+'Users'+r'/[A-Za-z0-9_]'
        if re.search(home_pattern,body):issues.append('Personal absolute home path '+rel)
        if '\ufffd' in body:issues.append('Replacement glyph '+rel)
        if path.suffix=='.py':
            try:ast.parse(body,filename=rel)
            except SyntaxError as exc:issues.append('Python syntax '+rel+': '+str(exc))
        if path.suffix=='.json':
            try:json.loads(body)
            except ValueError:issues.append('Invalid JSON '+rel)
        if path.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',body):
                if '://' in target or target.startswith(('#','mailto:')):continue
                loc=unquote(target.split('#',1)[0])
                if loc and not (path.parent/loc).exists():issues.append('Broken link '+rel+': '+target)
    return {'ok':not issues,'files_scanned':scans,'scope':'Basic structure, local links and selected sensitive patterns only; not full YAML/JSON Schema or security validation.','issues':issues}

if __name__=='__main__':
    result=check_project();print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
