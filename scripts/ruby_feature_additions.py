"""Check corpora/features/ruby-feature-additions/v1 (F40 additive generation).

Rows come from archive/capture-f40-additions.rb run unchanged at two Ruby heads
(plurimath-ruby 9c90094a with unitsml 0.6.14, and 0a1df68 with unitsml-ruby
de4f5b9). The two payloads must be byte-equal, every archived file must match
its seal, and vectors.json must re-derive byte-equal from the payload.

  python -I scripts/ruby_feature_additions.py check | build
"""
import hashlib, json, sys
from pathlib import Path
GEN = Path(__file__).resolve().parents[1] / "corpora/features/ruby-feature-additions/v1"
A, B = GEN / "archive/f40-additions-9c90094.jsonl", GEN / "archive/f40-additions-0a1df68.jsonl"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def vectors():
    rows = [json.loads(l) for l in A.read_text(encoding="utf-8").splitlines()]
    cases = []
    for r in rows:
        fam = r.pop("family"); rid = r.pop("id")
        expected = {k: r.pop(k) for k in ("outcome", "value", "unit", "accuracy", "norm_text", "reparsed_norm_text",
                                           "idempotent", "error_class", "message") if k in r}
        cases.append({"id": rid, "family": fam, "input": r, "expected": expected,
                      "comparison": "exact equality of the wire-encoded values (rational/decimal/binary64/symbol)"})
    return json.dumps({"schema": "unitsml-testsuite-ruby-feature-additions/1", "count": len(cases), "cases": cases},
                      ensure_ascii=False, indent=1) + "\n"

def check():
    ix = json.loads((GEN / "index.json").read_text(encoding="utf-8"))
    bad = [p for p, h in ix["archive_seals"].items() if sha(GEN / p) != h]
    res = {"bad_seals": bad, "heads_byte_equal": A.read_bytes() == B.read_bytes(),
           "vectors_rederived": vectors() == (GEN / "vectors.json").read_text(encoding="utf-8"),
           "vectors_sha": sha(GEN / "vectors.json") == ix["files"]["vectors.json"]}
    print(json.dumps(res)); return 0 if not bad and all(v for k, v in res.items() if k != "bad_seals") else 1

def build():
    (GEN / "vectors.json").write_text(vectors(), encoding="utf-8"); return 0

if __name__ == "__main__":
    sys.exit({"check": check, "build": build}[sys.argv[1]]())
