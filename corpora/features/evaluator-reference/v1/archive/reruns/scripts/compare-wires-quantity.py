"""Compare the 3 frozen quantity wires with the Ruby probe on Ruby-observable fields."""
import json, sys
from fractions import Fraction as Q
D, WIRES = sys.argv[1:3]
w = {c['id']: json.loads(c['expected_wire']) for c in json.load(open(WIRES))['cases'] if c['profile'] == 'quantity'}
out = []
for r in json.load(open(f'{D}/rerun/quantity-probe.json')):
    g = w[r['id']]
    if r['ok']:
        conv = g['result']['converted']
        dims = {k: Q(v) for k, v in conv['dimensions'].items()}
        ok = (g['ok'] and Q(conv['magnitude']) == Q(r['converted']['magnitude'])
              and dims == {k: Q(v) for k, v in r['dimensions'].items()}
              and g['result']['accuracy'] == {'symbol': r['accuracy']})
        basis = 'converted magnitude, dimensions, accuracy'
    else:
        ok = g['ok'] is False
        basis = f"both refuse (Ruby {r['error_class']}; wire {g['error']['code']} with native parser offset, no Ruby equivalent)"
    out.append({'id': r['id'], 'agree': ok, 'basis': basis})
print(json.dumps({'checked': len(out), 'agree': sum(x['agree'] for x in out), 'rows': out}, indent=1))
