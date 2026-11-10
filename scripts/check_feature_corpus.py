"""Check corpora/features seals, counts and structure (stdlib only).

Usage: python scripts/check_feature_corpus.py [REPO_ROOT]
Exit 0 when every check passes; prints one line per check.
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..'))
FEAT = os.path.join(ROOT, 'corpora', 'features')
failures = []


def check(name, ok):
    print('%s %s' % ('ok  ' if ok else 'FAIL', name))
    if not ok:
        failures.append(name)


def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load(name):
    with open(os.path.join(FEAT, name), encoding='utf-8') as fh:
        return json.load(fh)


idx = load('index.json')
for name, digest in idx['files'].items():
    check('seal %s' % name, sha(os.path.join(FEAT, name)) == digest)
for entry in idx['archive']:
    check('archive seal %s' % entry['path'], sha(os.path.join(ROOT, entry['path'])) == entry['sha256'])
for path, seal in idx['preserved_vectors'].items():
    blob = subprocess.check_output(['git', '-C', ROOT, 'hash-object', path], text=True).strip()
    check('preserved %s' % path, blob == seal['git_blob'])

gum = load('gum-mcm-profiles.json')
check('gum counts', gum['counts'] == {'H1': 2, 'extended': 11} and len(gum['cases']) == 13)
check('gum ids unique', len({c['id'] for c in gum['cases']}) == 13)
archived = {}
for entry in idx['archive']:
    with open(os.path.join(ROOT, entry['path']), encoding='utf-8') as fh:
        for case in json.load(fh)['cases']:
            archived[case['id']] = case
check('gum results verbatim from archive', all(c['result'] == archived[c['id']]['result'] for c in gum['cases']))
check('gum seeds/probability/stop present', all(
    c['result']['engine'].get('initial_seeds') and c['result']['engine'].get('final_state')
    and c['result'].get('probability') and 'stabilized' in c['stop'] for c in gum['cases']))
check('gum all passed', all(c['passed'] for c in gum['cases']))

uq = load('unitsml-quantities.json')
check('unitsml counts', uq['counts']['cases'] == len(uq['cases']))
check('unitsml ids unique', len({c['id'] for c in uq['cases']}) == len(uq['cases']))
for c in uq['cases']:
    if c['outcome'] == 'ok' and 'value' in c['result']:
        n, d = (int(x) for x in c['result']['value']['rational'].split('/'))
        dec = c['result']['value'].get('decimal')
        if dec is not None:
            from fractions import Fraction
            check('decimal agrees %s' % c['id'], Fraction(dec) == Fraction(n, d))
refusals = [c for c in uq['cases'] if c['kind'] == 'refusal']
check('refusals all typed errors', all(c['outcome'] == 'error' and c['error_class'] for c in refusals))
sys.exit(1 if failures else 0)
