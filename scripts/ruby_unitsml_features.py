"""Check corpora/features/ruby-unitsml-features/v1 (F40 additive generation).

Rows come from archive/capture-unitsml-features.rb run at unitsml-ruby 2337a12
(branch claude/f40-ruby-features-20261111) in two separate processes. The two
payloads must be byte-equal, every archived file must match its seal, and
vectors.json must re-derive byte-equal from the payload.

  python -I scripts/ruby_unitsml_features.py check | build
"""
import hashlib, json, sys
from pathlib import Path
GEN = Path(__file__).resolve().parents[1] / "corpora/features/ruby-unitsml-features/v1"
A = GEN / "archive/unitsml-features-2337a12.jsonl"
B = GEN / "archive/unitsml-features-2337a12-rerun.jsonl"
OUT = ("outcome", "value", "unit", "kind", "scale", "converted_value", "converted_unit", "primary", "by_order",
       "order_independent", "first_reference_is_primary", "error_class")
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def vectors():
    cases = []
    for line in A.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        fam = r.pop("family"); rid = r.pop("id")
        expected = {k: r.pop(k) for k in OUT if k in r}
        cases.append({"id": rid, "family": fam, "input": r, "expected": expected,
                      "comparison": "exact equality of the wire-encoded values; error rows compare error_class"})
    return json.dumps({"schema": "unitsml-testsuite-ruby-unitsml-features/1", "count": len(cases), "cases": cases},
                      ensure_ascii=False, indent=1) + "\n"

def check():
    ix = json.loads((GEN / "index.json").read_text(encoding="utf-8"))
    bad = [p for p, h in ix["archive_seals"].items() if sha(GEN / p) != h]
    res = {"bad_seals": bad, "runs_byte_equal": A.read_bytes() == B.read_bytes(),
           "vectors_rederived": vectors() == (GEN / "vectors.json").read_text(encoding="utf-8"),
           "vectors_sha": sha(GEN / "vectors.json") == ix["files"]["vectors.json"]}
    print(json.dumps(res)); return 0 if not bad and all(v for k, v in res.items() if k != "bad_seals") else 1

def build():
    (GEN / "vectors.json").write_text(vectors(), encoding="utf-8"); return 0

if __name__ == "__main__":
    sys.exit({"check": check, "build": build}[sys.argv[1]]())
