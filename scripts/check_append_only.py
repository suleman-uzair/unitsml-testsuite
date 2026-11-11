#!/usr/bin/env python3
"""Fail when a change modifies, deletes, renames or retypes any file under
corpora/ that already exists in the base revision. Frozen generations and
archives are append-only: a new generation is added beside the old one, never
written over it.

Usage: python scripts/check_append_only.py <base-ref> [<head-ref>]
"""
import subprocess
import sys


def main(argv):
    if len(argv) < 2:
        print("usage: check_append_only.py <base-ref> [<head-ref>]", file=sys.stderr)
        return 2
    base, head = argv[1], argv[2] if len(argv) > 2 else "HEAD"
    merge_base = subprocess.run(["git", "merge-base", base, head], check=True,
                                capture_output=True, text=True).stdout.strip()
    out = subprocess.run(
        ["git", "diff", "--no-renames", "--name-status", "--diff-filter=DMT", merge_base, head, "--", "corpora"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    changed = [line for line in out.splitlines() if line]
    added = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", merge_base, head, "--", "corpora"],
        check=True, capture_output=True, text=True,
    ).stdout.split()
    print({"merge_base": merge_base, "head": head, "added": len(added), "rewritten_or_removed": changed})
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
