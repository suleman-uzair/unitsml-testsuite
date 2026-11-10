"""Build or check corpora/features/host-evaluator/v1 (stdlib only).

Usage:
  python scripts/host_evaluator_vectors.py build PACKET_DIR [REPO_ROOT]
      Copy the producer payloads verbatim from an F40 packet into archive/
      (refusing on any manifest/provenance digest mismatch) and regenerate
      vectors.json and index.json from the archived bytes.
  python scripts/host_evaluator_vectors.py check [REPO_ROOT]
      Re-verify every seal, re-derive vectors.json/index.json from archive/
      and require byte equality, and validate each case against the schema
      rules. Exit 0 only when every check passes.

Expected values are never computed here: every input/expected field is the
producer's JSON row, copied unchanged. Rows are addressed by (file, line).
"""
import hashlib
import json
import os
import shutil
import sys

SCHEMA_ID = 'unitsml-testsuite-host-evaluator-vectors/1'
REL = os.path.join('corpora', 'features', 'host-evaluator', 'v1')
PAYLOADS = [
    'handoffs/F40/extended-ruby-producer.jsonl',
    'handoffs/F40/extended-ruby-refusals.jsonl',
    'handoffs/F40/extended-ruby-coverage.jsonl',
    'handoffs/F40/producer-provenance.json',
    'handoffs/F40/capture-ruby-features.rb',
    'handoffs/F40/capture-ruby-quantity.rb',
    'handoffs/F21/h2-publication-boundary.json',
]
PROBES = {'producer': 'extended-ruby-producer', 'refusals': 'extended-ruby-refusals',
          'coverage': 'extended-ruby-coverage'}

# Family labels per (probe, 0-based line). Labels name what the producer
# example/method says; they do not assert any value.
FAMILIES = {
    'producer': [(0, 0, 'h2_raw_paired_data'),
                 (1, 1, 'h2_first_approach_raw_inputs'),
                 (2, 2, 'h2_first_approach_rounded_summary_inputs'),
                 (3, 3, 'h2_second_output_approach'),
                 (4, 5, 'annex_h_type_a_covariance'),
                 (6, 8, 'grouped_statistics'),
                 (9, 25, 'conformity')],
    'refusals': [(0, 9, 'gum_components_and_input_validation'),
                 (10, 13, 'series_statistics'),
                 (14, 14, 'voltage_current_conversion')],
    'coverage': [(0, 15, 'coverage_factors'),
                 (16, 29, 'decimal_output'),
                 (30, 32, 'gum_model_adequacy')],
}
REQUESTED = {
    'H2 raw paired data': ['h2_raw_paired_data', 'h2_first_approach_raw_inputs'],
    'H2 rounded summary input': ['h2_first_approach_rounded_summary_inputs'],
    'H2 second output approach': ['h2_second_output_approach'],
    'conformity': ['conformity'],
    'grouped/series statistics': ['grouped_statistics', 'series_statistics'],
    'voltage-current conversion': ['voltage_current_conversion'],
    'GUM model adequacy/refusals': ['gum_model_adequacy', 'gum_components_and_input_validation'],
}
MISSING = {
    'h2_published_last_digit_agreement': 'unresolved by producer: see h2_publication_boundary; needs original unrounded five triples or the source rounding convention',
    'distinct_named_power_class': 'not evidenced: the only row shows kV*A with dimension L2 M T-3 converting to kW; no named power quantity class is asserted',
    'gum_mcm_rerun': 'not rerun here; validate_coverage rows are producer outputs and MCM profiles stay in gum-mcm-profiles.json',
    'spec_file_digests': 'producer-reported only; plurimath spec sources are not in this checkout, so the digests are not re-verified locally',
    'plurimath_exact_head_source': 'producer head 9c90094a is recorded from producer-provenance.json; no plurimath source archive is included',
}
# Producer rows carry guard_digits=50 while the boundary file prints ~66
# digits, so rows link to a boundary profile by a fixed leading-character
# prefix only (identification, not an equality or rounding claim).
PROFILE_LINK_CHARS = 30
SPEC_HINTS = {
    'h2': 'JCGM 100:2008 Annex H.2 (Tables H.2/H.3)',
    'annex_h_type_a_covariance': 'JCGM 100:2008 Annex H.4',
    'grouped_statistics': 'JCGM 100:2008 Annex H.5',
    'conformity': 'JCGM 106:2012',
    'coverage_factors': 'JCGM 100:2008 Annex G',
    'gum_model_adequacy': 'JCGM 101:2008 clause 8 (validation of GUF by MCM)',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, 'rb') as fh:
        return fh.read()


def dump(obj):
    return (json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + '\n').encode('utf-8')


def family_of(probe, line):
    for lo, hi, fam in FAMILIES[probe]:
        if lo <= line <= hi:
            return fam
    raise ValueError('unlabelled row %s:%d' % (probe, line))


def spec_hint(fam):
    return SPEC_HINTS.get('h2' if fam.startswith('h2_') else fam)


def derive(vroot):
    """Derive (vectors_bytes, index_bytes) from archived payloads only."""
    arch = os.path.join(vroot, 'archive')
    prov_raw = read(os.path.join(arch, 'handoffs/F40/producer-provenance.json'))
    prov = json.loads(prov_raw)
    boundary_raw = read(os.path.join(arch, 'handoffs/F21/h2-publication-boundary.json'))
    boundary = json.loads(boundary_raw)
    cases = []
    for probe, stem in PROBES.items():
        rel = 'handoffs/F40/%s.jsonl' % stem
        data = read(os.path.join(arch, rel))
        lines = data.split(b'\n')
        if lines and lines[-1] == b'':
            lines.pop()
        for n, line in enumerate(lines):
            row = json.loads(line)
            fam = family_of(probe, n)
            case = {'id': '%s-%02d' % (probe, n), 'family': fam,
                    'source': {'payload': rel, 'line': n + 1, 'row_sha256': sha(line)}}
            if 'spec' in row:
                case['source'].update({'spec': row['spec'], 'spec_line': row['line'],
                                       'spec_sha256_reported': prov['probes'][stem]['specs'].get(row['spec']),
                                       'example': row['example']})
                case['method'] = row['method']['symbol']
                case['input'] = {'args': row['args'], 'kwargs': row['kwargs']}
                if 'error' in row:
                    case['expected'] = {'outcome': 'error', 'error_class': row['error']['type'],
                                        'message': row['error']['message']}
                else:
                    case['expected'] = {'outcome': 'ok', 'result': row['result']}
            else:  # unitsml quantity capture (capture-ruby-quantity.rb)
                case['source'].update({'script': 'handoffs/F40/capture-ruby-quantity.rb', 'example': row['id']})
                case['method'] = 'evaluate_quantity+convert_to'
                case['input'] = {'formula': row['formula'], 'syntax': 'asciimath', 'bindings': row['inputs'],
                                 'convert_to': row['converted']['unit']}
                case['expected'] = {'outcome': 'ok', 'result': {'outcome': row['outcome'], 'converted': row['converted']}}
                case['claims'] = {'named_power_class': 'not asserted',
                                  'basis': 'only the kV*A -> kW conversion succeeded and the dimension vector is recorded'}
            hint = spec_hint(fam)
            if hint:
                case['source']['standard'] = hint
            if fam.startswith('h2_first_approach'):
                key = 'raw_printed_inputs_u' if fam.endswith('raw_inputs') else 'rounded_summary_profile_u'
                case['input_profile'] = key
                case['publication_boundary'] = {'profile_u': boundary[key],
                                                'link': 'standard_uncertainties match profile_u on the leading %d characters; row precision is guard_digits=%s' % (PROFILE_LINK_CHARS, row['result'].get('guard_digits')),
                                                'reported_table_h3_u': boundary['reported_table_h3_u'],
                                                'published_last_digit': 'unresolved'}
            cases.append(case)
    counts = {}
    for c in cases:
        counts[c['family']] = counts.get(c['family'], 0) + 1
    vectors = {
        'schema': SCHEMA_ID, 'card': 'F40', 'version': 1,
        'producer': {'plurimath_head': prov['head'], 'runtime': prov['runtime'], 'gems': prov['gems'],
                     'active_lock_sha256': prov['active_lock_sha256'],
                     'provenance': 'archive/handoffs/F40/producer-provenance.json'},
        'comparison': {
            'rational': 'exact [numerator, denominator] string equality',
            'decimal': 'exact string equality (producer guard digits are part of the input)',
            'binary64': 'exact hex bit pattern for the same numeric_backend; no cross-backend bitwise claim',
            'error': 'error_class exact; message informative only',
            'raw_vs_rounded': 'h2_first_approach_raw_inputs and h2_first_approach_rounded_summary_inputs are distinct cases and must not be merged or substituted',
        },
        'h2_publication_boundary': {'source': boundary['source'], 'status': boundary['status'],
                                    'unsupported_assertion': boundary['unsupported_assertion'],
                                    'required_next_data': boundary['required_next_data'],
                                    'published_last_digit': 'unresolved',
                                    'payload': 'archive/handoffs/F21/h2-publication-boundary.json'},
        'counts': {'cases': len(cases), 'errors': sum(c['expected']['outcome'] == 'error' for c in cases),
                   'families': dict(sorted(counts.items()))},
        'cases': cases,
    }
    vbytes = dump(vectors)
    seals = {p: sha(read(os.path.join(arch, p))) for p in PAYLOADS}
    index = {
        'schema': 'unitsml-testsuite-host-evaluator-index/1', 'card': 'F40', 'version': 1,
        'files': {'vectors.json': sha(vbytes),
                  'schema/host-evaluator-case.schema.json': sha(read(os.path.join(vroot, 'schema/host-evaluator-case.schema.json')))},
        'payload_seals': seals,
        'fixture_seal': sha(b''.join(('%s\0%s\n' % (p, seals[p])).encode() for p in sorted(seals))),
        'fixture_seal_method': 'sha256 over sorted payload path NUL sha256 LF',
        'requested_coverage': {k: {'families': v, 'cases': sum(counts.get(f, 0) for f in v)} for k, v in REQUESTED.items()},
        'missing_coverage': MISSING,
        'replay': 'python scripts/host_evaluator_vectors.py check; producer replay: run capture-ruby-*.rb with F40_OUTPUT under the pinned runtime/gems and compare row_sha256',
    }
    return vbytes, dump(index)


def build(packet, root):
    vroot = os.path.join(root, REL)
    man = json.loads(read(os.path.join(packet, 'manifest.json')))
    prov = json.loads(read(os.path.join(packet, 'handoffs/F40/producer-provenance.json')))
    for p in PAYLOADS:
        digest = sha(read(os.path.join(packet, p)))
        if man['sha256'].get(p) != digest:
            sys.exit('refuse: manifest digest mismatch %s' % p)
    for stem in PROBES.values():
        if sha(read(os.path.join(packet, 'handoffs/F40/%s.jsonl' % stem))) != prov['probes'][stem]['sha256']:
            sys.exit('refuse: provenance digest mismatch %s' % stem)
    for p in PAYLOADS:
        dst = os.path.join(vroot, 'archive', p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(packet, p), dst)
    vbytes, ibytes = derive(vroot)
    for name, data in (('vectors.json', vbytes), ('index.json', ibytes)):
        with open(os.path.join(vroot, name), 'wb') as fh:
            fh.write(data)
    print('built %s cases=%d' % (REL, json.loads(vbytes)['counts']['cases']))


def check(root):
    vroot = os.path.join(root, REL)
    fails = []

    def ok(name, cond):
        print('%s %s' % ('ok  ' if cond else 'FAIL', name))
        if not cond:
            fails.append(name)

    try:
        index = json.loads(read(os.path.join(vroot, 'index.json')))
        for p, digest in index['payload_seals'].items():
            ok('payload seal %s' % p, sha(read(os.path.join(vroot, 'archive', p))) == digest)
        for p, digest in index['files'].items():
            ok('file seal %s' % p, sha(read(os.path.join(vroot, p))) == digest)
        prov = json.loads(read(os.path.join(vroot, 'archive/handoffs/F40/producer-provenance.json')))
        for stem in PROBES.values():
            p = 'handoffs/F40/%s.jsonl' % stem
            data = read(os.path.join(vroot, 'archive', p))
            ok('provenance digest %s' % stem, sha(data) == prov['probes'][stem]['sha256'])
            ok('provenance rows %s' % stem, data.count(b'\n') == prov['probes'][stem]['rows'])
        ok('boundary digest', sha(read(os.path.join(vroot, 'archive/handoffs/F21/h2-publication-boundary.json')))
           == prov['h2_published_boundary_sha256'])
        vbytes, ibytes = derive(vroot)
        ok('vectors.json re-derived byte-equal', vbytes == read(os.path.join(vroot, 'vectors.json')))
        ok('index.json re-derived byte-equal', ibytes == read(os.path.join(vroot, 'index.json')))
        vec = json.loads(vbytes)
        schema = json.loads(read(os.path.join(vroot, 'schema/host-evaluator-case.schema.json')))
        req, outcomes = schema['required'], schema['properties']['expected']['properties']['outcome']['enum']
        ids = [c['id'] for c in vec['cases']]
        ok('case ids unique', len(ids) == len(set(ids)))
        ok('cases match schema required/outcome', all(
            all(k in c for k in req) and c['expected']['outcome'] in outcomes
            and ('result' in c['expected']) == (c['expected']['outcome'] == 'ok')
            and (c['expected']['outcome'] == 'ok' or c['expected']['error_class']) for c in vec['cases']))
        pin = prov['gems']['plurimath']

        def versions(o):
            if isinstance(o, dict):
                if o.get('name') == 'plurimath' and 'version' in o:
                    yield o['version']
                for v in o.values():
                    yield from versions(v)
            elif isinstance(o, list):
                for v in o:
                    yield from versions(v)
        found = [v for c in vec['cases'] for v in versions(c['expected'])]
        ok('engine versions pinned to %s (%d rows)' % (pin, len(found)), found and set(found) == {pin})
        by = {c['family']: c for c in vec['cases'] if c['family'].startswith('h2_first_approach')}
        raw, rnd = by['h2_first_approach_raw_inputs'], by['h2_first_approach_rounded_summary_inputs']
        def u_of(case):
            return [next(iter(v.values())) if isinstance(v, dict) else v
                    for v in case['expected']['result']['standard_uncertainties']]
        n = PROFILE_LINK_CHARS
        ok('raw profile u linked to raw row only (%d-char prefix)' % n, all(
            a[:n] == b[:n] and a[:n] != c[:n]
            for a, b, c in zip(u_of(raw), raw['publication_boundary']['profile_u'], rnd['publication_boundary']['profile_u'])))
        ok('rounded profile u linked to rounded row only (%d-char prefix)' % n, all(
            a[:n] == b[:n] and a[:n] != c[:n]
            for a, b, c in zip(u_of(rnd), rnd['publication_boundary']['profile_u'], raw['publication_boundary']['profile_u'])))
        ok('published last digit unresolved', vec['h2_publication_boundary']['published_last_digit'] == 'unresolved')
        vi = [c for c in vec['cases'] if c['family'] == 'voltage_current_conversion']
        ok('V*I: no named power class asserted', len(vi) == 1 and vi[0]['claims']['named_power_class'] == 'not asserted')
        ok('requested coverage nonempty', all(v['cases'] > 0 for v in index['requested_coverage'].values()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        ok('readable/derivable: %s: %s' % (type(exc).__name__, exc), False)
    print('%d failure(s)' % len(fails))
    return 1 if fails else 0


if __name__ == '__main__':
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if len(sys.argv) >= 3 and sys.argv[1] == 'build':
        build(os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else here)
    elif len(sys.argv) >= 2 and sys.argv[1] == 'check':
        sys.exit(check(os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else here))
    else:
        sys.exit(__doc__)
