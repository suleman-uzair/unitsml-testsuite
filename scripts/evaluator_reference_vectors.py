"""Build or check corpora/features/evaluator-reference/v1 (F40, new generation).

The generation freezes the 388 canonical evaluator request/expected wires that
the native engines were qualified against (R30 all-wires.json), together with
byte-for-byte archives of every source fixture they were projected from and of
the independent Ruby reference re-runs that accept them.

  python -I scripts/evaluator_reference_vectors.py check
  python -I scripts/evaluator_reference_vectors.py build

`check` verifies every archive seal in index.json, the fixture seal, and that
vectors.json re-derives byte-equal from the archive. Stdlib only.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "corpora/features/evaluator-reference/v1"
ARCHIVE = GEN / "archive"
WIRES = ARCHIVE / "R30/coverage-validation/all-wires.json"
FIXTURES = ARCHIVE / "plurimath-rs/fixtures"
ACCEPTANCE = GEN / "acceptance.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_rows(name, data):
    """(id, request-or-None) pairs a fixture contributes."""
    if name == "gum-annex":
        rows = []
        for key in ("h1", "joint_gaussian"):
            value = data[key]
            for item in value if isinstance(value, list) else [value]:
                # h1 is a single unnamed profile; R30 gum-followup/prove-abi.py names its wire h1-lpu-analytic
                rows.append((item.get("id", "h1-lpu-analytic"), item.get("request")))
        return rows
    if name == "quantity-f40":
        return [(data["source"].get("case_id"), data.get("request"))]
    out = []
    for case in data.get("cases", []):
        req = case.get("request")
        if req is None and "request_json" in case:
            try:
                req = json.loads(case["request_json"])
            except ValueError:
                req = case["request_json"]
        out.append((case.get("id"), req))
    return out


def source_index():
    index = {}
    for path in sorted(FIXTURES.glob("*.json")):
        name = path.stem
        for case_id, req in fixture_rows(name, json.loads(path.read_text(encoding="utf-8"))):
            index.setdefault(case_id, []).append((name, req))
    return index


def parse_request(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


def classify(request, expected):
    req = request if isinstance(request, dict) else {}
    params = req.get("parameters") or {}
    seeds = params.get("seeds") or params.get("initial_seeds")
    method = req.get("method")
    stochastic = bool(seeds) or method == "monte_carlo"
    mode = req.get("mode")
    return {
        "schema": req.get("schema"),
        "method": method,
        "numeric_mode": mode,
        "precision": "approximate" if (mode == "approximate" or stochastic) else "exact",
        "seeds": seeds,
        "outcome": "ok" if expected.get("ok") else "error",
        "error_code": (expected.get("error") or {}).get("code") if not expected.get("ok") else None,
    }


def build_vectors():
    wires = json.loads(WIRES.read_text(encoding="utf-8"))["cases"]
    sources = source_index()
    acc = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    acceptance = acc["families"]
    for case_id, family in acc.get("extra_sources", {}).items():
        sources.setdefault(case_id, []).append((family, None))
    seen = {}
    rows = []
    for wire in wires:
        request = parse_request(wire["request_json"])
        expected = json.loads(wire["expected_wire"])
        candidates = sources.get(wire["id"], [])
        matched = [n for n, r in candidates if r is None or r == request or r == wire["request_json"]]
        if not matched and candidates:  # fixture stores the request in a pre-wire shape; the id is unique
            matched = [n for n, _ in candidates]
        family = matched[0] if len(set(matched)) == 1 else (matched[0] if matched else "unmapped")
        if len(set(matched)) > 1:
            family = "+".join(sorted(set(matched)))
        seen[wire["id"]] = seen.get(wire["id"], 0) + 1
        key = wire["id"] if seen[wire["id"]] == 1 else f'{wire["id"]}#{seen[wire["id"]]}'
        rows.append({
            "key": key,
            "id": wire["id"],
            "profile": wire["profile"],
            "family": family,
            **classify(request, expected),
            "acceptance": acceptance.get(family.split("+")[0], {"status": "unmapped"})["status"],
            "request_json": wire["request_json"],
            "expected_wire": wire["expected_wire"],
        })
    return {
        "schema": "unitsml-testsuite-evaluator-reference/1",
        "comparison": "request_json is sent verbatim; expected_wire is compared byte-exact (canonical JSON text). "
                      "Stochastic rows replay only with identical method, generator and seeds; precision=approximate marks "
                      "rows whose value is a declared approximation, not a looser comparison.",
        "count": len(rows),
        "cases": rows,
    }


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def check():
    index = json.loads((GEN / "index.json").read_text(encoding="utf-8"))
    bad = [p for p, h in index["archive_seals"].items() if sha(GEN / p) != h]
    lines = "".join(f"{p}\0{h}\n" for p, h in sorted(index["archive_seals"].items()))
    seal_ok = hashlib.sha256(lines.encode()).hexdigest() == index["fixture_seal"]
    rebuilt = dump(build_vectors())
    vectors_ok = rebuilt == (GEN / "vectors.json").read_text(encoding="utf-8")
    vectors_sha_ok = sha(GEN / "vectors.json") == index["files"]["vectors.json"]
    acc_ok = sha(ACCEPTANCE) == index["files"]["acceptance.json"]
    result = {"archive_files": len(index["archive_seals"]), "bad_seals": bad, "fixture_seal": seal_ok,
              "vectors_rederived_byte_equal": vectors_ok, "vectors_sha": vectors_sha_ok, "acceptance_sha": acc_ok}
    print(json.dumps(result))
    return 0 if not bad and seal_ok and vectors_ok and vectors_sha_ok and acc_ok else 1


def build():
    (GEN / "vectors.json").write_text(dump(build_vectors()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit({"check": check, "build": build}[sys.argv[1]]())
