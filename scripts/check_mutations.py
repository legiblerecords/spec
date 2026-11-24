#!/usr/bin/env python3
"""Check that the vectors catch a checker that skips a rule.

Runs scripts/check_vectors.py once per mutation, with LEGIBLE_VECTORS_MUTATION set so
that the checker skips one check, and fails unless every run then reports problems.
A mutation that nothing catches means a rule has no vector that isolates it.

    python scripts/check_mutations.py

Needs what check_vectors.py needs.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Each turns off one check in check_vectors.py.
MUTATIONS = {
    "feed-sig-verify": "feed.sig is never verified",
    "manifest-sig-verify": "manifest.sig is never verified",
    "zip-names": "zip entry names aren't checked",
    "future-skew": "timestamps far ahead of the clock are allowed",
    "served-key-set": "the key set served on a poll is decided but never used",
    "revocation-clears": "a revocation doesn't clear what the key signed",
    "forget-unaccepted": "forget on unaccepted revocation: a set that isn't held clears state",
    "revocation-drops-floors": "a revocation drops the replay floors instead of keeping them",
    "pin-alias": "pin alias allowed: a pinned key a key set lists under another id is trusted, and endorses",
    "record-set-order": "a record set's lines needn't be sorted by id",
}


def main():
    failures = 0
    for name, what in MUTATIONS.items():
        env = dict(os.environ, LEGIBLE_VECTORS_MUTATION=name)
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_vectors.py")],
                             env=env, capture_output=True, text=True)
        caught = [line for line in run.stdout.splitlines() if line.startswith("FAIL ")]
        if run.returncode == 1 and caught:
            print(f"ok   {name} ({what}): caught by {len(caught)} vector(s)")
            for line in caught:
                print(f"       {line[5:]}")
        else:
            failures += 1
            print(f"FAIL {name} ({what}): check_vectors.py exited {run.returncode} with no problems")
    print(f"{len(MUTATIONS)} mutations checked, {failures} not caught")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
