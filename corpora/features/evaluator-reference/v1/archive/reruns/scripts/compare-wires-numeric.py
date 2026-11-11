"""Compare frozen all-wires numeric rows (numeric + annex_h_numeric profiles) with the Ruby re-run wires, by id + request."""
import json, sys, collections
D, WIRES = sys.argv[1:3]
def load(t):
    try: return json.loads(t)
    except ValueError: return t
rr = {}
for s in ['bignum', 'nonfinite', 'supplemental', 'validation', 'numeric-v1', 'numeric-annex-h']:
    for c in json.load(open(f'{D}/rerun/{s}-ruby-reference.json'))['cases']:
        req = load(c['request_json']) if 'request_json' in c else c['request']
        rr.setdefault(c['id'], []).append((req, c['expected_wire']))
res = collections.Counter(); bad = []
for c in json.load(open(WIRES))['cases']:
    if c['profile'] not in ('numeric', 'annex_h_numeric'):
        continue
    req = load(c['request_json'])
    m = [e for r, e in rr.get(c['id'], []) if r == req]
    k = 'no-rerun-match' if not m else ('byte_equal' if c['expected_wire'] in m else 'diff')
    res[k] += 1
    if k != 'byte_equal': bad.append(c['id'])
print(json.dumps({'counts': res, 'non_equal_ids': bad}))
