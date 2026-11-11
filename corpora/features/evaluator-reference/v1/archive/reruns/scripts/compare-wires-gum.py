"""Compare frozen all-wires GUM/quantity rows (native-observed wires) with Ruby expectations.

Ruby side: this task's re-runs where available (coverage-validation @0a1df68,
annex methods + conformity edges @ede5978), otherwise the frozen fixture's
Ruby-derived `expected` (whose source producer rows were re-run byte-identical).
Projection follows R30 gum-followup/prove-abi.py: drop engine.name/version;
an error compares code == last segment of error_class and the message.
"""
import json, sys, collections
D, WIRES, FX = sys.argv[1:4]

def proj(v):
    if isinstance(v, list):
        return [proj(x) for x in v]
    if isinstance(v, dict):
        v = {k: proj(x) for k, x in v.items()}
        if isinstance(v.get('engine'), dict):
            v['engine'] = {k: x for k, x in v['engine'].items() if k not in {'name', 'version'}}
        return v
    return v

def symbolize(exp):
    # prove-abi.py wraps these two MCM fields as {"symbol": ...} before comparing
    r = dict(exp)
    for k in ('method', 'precision_convention'):
        if isinstance(r.get(k), str):
            r[k] = {'symbol': r[k]}
    return r

ruby = {}
def add(fam, rows):
    for c in rows:
        ruby.setdefault(c['id'], []).append((fam, c.get('request'), c['expected']))
add('coverage-validation', json.load(open(f'{D}/rerun/coverage-validation-reference.json'))['cases'])
cv = json.load(open(f'{D}/rerun/coverage-validation-reference.json'))
ruby.setdefault('validation-source-normal-170k', []).append(('coverage-validation', cv['actual_monte_carlo_request'], {'outcome': 'ok', 'result': cv['actual_monte_carlo']}))
add('gum-annex-methods', json.load(open(f'{D}/rerun/annex-methods-reference.json'))['cases'])
add('gum-annex-methods', json.load(open(f'{D}/rerun/chain-reference.json'))['gum_cases'])
add('gum-conformity(edge)', json.load(open(f'{D}/rerun/conformity-edge-reference.json'))['cases'])
for name in ['gum-conformity', 'gum-f40', 'gum-mcm', 'gum-mcm-joint-rational']:
    for c in json.load(open(f'{FX}/{name}.json'))['cases']:
        if c['id'] not in ruby or name != 'gum-conformity':
            ruby.setdefault(c['id'], []).append((name + '(fixture)', c.get('request'), c['expected']))
ga = json.load(open(f'{FX}/gum-annex.json'))['h1']
ruby.setdefault('h1-lpu-analytic', []).append(('gum-annex(fixture,subset)', ga['request'], {'outcome': 'ok', 'subset': ga['expected']}))

res = collections.Counter(); rows = []
for w in json.load(open(WIRES))['cases']:
    if w['profile'] in ('numeric', 'annex_h_numeric', 'quantity_register'):
        continue
    got = json.loads(w['expected_wire']); req = json.loads(w['request_json'])
    verdict = 'no-ruby-expectation'; fam = None
    for fam, rreq, exp in ruby.get(w['id'], []):
        if rreq is not None and proj(rreq) != proj(req) and rreq != req:
            pass  # requests are wire-encoded differently; id match is the key here
        if 'outcome' not in exp:
            # MCM fixtures store the Ruby/GHA result fields directly (no engine block):
            # every stored field must equal the wire result (method/precision_convention symbol-wrapped).
            sub = symbolize(exp)
            def field_ok(k, v):
                if k == 'engine':  # replay key: Ruby engine fields (minus name/version) must all appear unchanged
                    ge = got['result'].get('engine') or {}
                    wrap = lambda a, b: {'symbol': b} if a == 'joint_distribution' and isinstance(b, str) else b  # as R30 verify-native.py
                    return all(ge.get(a) == wrap(a, b) for a, b in v.items() if a not in {'name', 'version'})
                return got['result'].get(k) == v
            ok = got.get('ok') is True and all(field_ok(k, v) for k, v in sub.items())
        elif exp.get('outcome') == 'ok' and 'subset' in exp:
            ok = got.get('ok') and all(got['result'].get(k) == v for k, v in exp['subset'].items())
        elif exp.get('outcome') == 'ok':
            ok = got.get('ok') is True and (proj(got['result']) == proj(exp['result']) or proj(got['result']) == proj(symbolize(exp['result'])))
        else:
            e = got.get('error') or {}
            ok = got.get('ok') is False and e.get('code') == exp['error_class'].rsplit('::', 1)[-1] and e.get('message') == exp['message']
        verdict = 'agree' if ok else 'disagree'
        if ok:
            break
    res[(w['profile'], fam, verdict)] += 1
    if verdict != 'agree':
        rows.append({'id': w['id'], 'profile': w['profile'], 'family': fam, 'verdict': verdict})
print(json.dumps({'counts': [{'profile': p, 'ruby_source': f, 'verdict': v, 'n': n} for (p, f, v), n in sorted(res.items(), key=str)], 'non_agree': rows}, indent=1))
