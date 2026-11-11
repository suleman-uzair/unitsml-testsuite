"""Compare re-run Ruby reference wires with the R30 reference outputs and the plurimath-rs fixtures."""
import json, sys
D, R30, FX = sys.argv[1:4]
out = {}
for s in ['bignum', 'nonfinite', 'supplemental', 'validation']:
    new = {c['id']: c['expected_wire'] for c in json.load(open(f'{D}/rerun/{s}-ruby-reference.json'))['cases']}
    old = {c['id']: c['expected_wire'] for c in json.load(open(f'{R30}/{s}-ruby-reference.json'))['cases']}
    fx = json.load(open(f'{FX}/numeric-{s}-v1.json'))['cases']
    fxw = {c['id']: c.get('expected_wire') for c in fx}
    out[s] = {'rerun': len(new), 'r30_reference': len(old), 'fixture': len(fxw),
              'rerun_eq_r30': sum(new[k] == old.get(k) for k in new),
              'rerun_eq_fixture': sum(new[k] == fxw.get(k) for k in new),
              'diff_ids_fixture': [k for k in new if new[k] != fxw.get(k)][:10]}
print(json.dumps(out, indent=1))
