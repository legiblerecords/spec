#!/usr/bin/env python3
"""Generate the signature test vectors, or check they are up to date.

    python scripts/make_vectors.py           write vectors/*.json
    python scripts/make_vectors.py --check   regenerate in memory; fail if a committed file differs

Ed25519 is deterministic, so the output is the same on every run.

TEST_SEEDS are TEST-ONLY private keys: they are published in this repository so
that every implementation can reproduce the vectors. Never use one to sign
anything real.

Each vector file is built by a function that returns its JSON value, and listed
in VECTOR_FILES, so a later part of the spec adds a file by adding a function
and an entry.

Needs: pip install cryptography
"""

import base64
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent

# Test-only seeds, by "<publisher>/<key id>".
TEST_SEEDS = {
    "acme.example/2026-11": bytes(range(32)),
    "acme.example/2025-06": bytes(range(32, 64)),
    "acme.example/2024-01": bytes(range(64, 96)),
    "other.example/1": bytes(range(96, 128)),
}

CONTEXTS = {
    "manifest": b"legible-records/v1 manifest\n",
    "feed": b"legible-records/v1 feed\n",
    "keys": b"legible-records/v1 keys\n",
}


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def private_key(name):
    return Ed25519PrivateKey.from_private_bytes(TEST_SEEDS[name])


def public_key(name):
    raw = private_key(name).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return b64url(raw)


def sign(name, context, message):
    """Sign CONTEXTS[context] + message with the test key `name`; base64url."""
    return b64url(private_key(name).sign(CONTEXTS[context] + message))


def stored_json(value):
    """JSON as a writer stores a record: sorted keys, 2-space indent, one trailing newline."""
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def signature_file(name, signature, alg="ed25519"):
    publisher, key = name.split("/", 1)
    return {"alg": alg, "publisher": publisher, "key": key, "signature": signature}


def sig_case(case_name, context, message, signature_file_, expect, key="acme.example/2026-11"):
    return {
        "name": case_name,
        "context": context,
        "public_key": public_key(key),
        "message_b64": b64url(message),
        "signature_file": signature_file_,
        "expect": expect,
    }


MANIFEST = stored_json({
    "$type": "org.legiblerecords.bundle",
    "version": 1,
    "files": [],
    "published_at": "2026-11-24T10:00:00Z",
    "feed": {"id": "acme.example/track", "stream": "policy-acknowledgments"},
})
FEED = stored_json({
    "$type": "org.legiblerecords.feed",
    "version": 1,
    "id": "acme.example/track",
    "updated_at": "2026-11-24T10:00:00Z",
})
KEYS = stored_json({
    "$type": "org.legiblerecords.keys",
    "version": 1,
    "publisher": "acme.example",
    "keys": [{
        "id": "2026-11",
        "alg": "ed25519",
        "public_key": public_key("acme.example/2026-11"),
        "created_at": "2026-11-24T00:00:00Z",
    }],
})

KEY = "acme.example/2026-11"
MESSAGES = {"manifest": MANIFEST, "feed": FEED, "keys": KEYS}


def signatures():
    cases = [
        sig_case(f"{ctx}-valid", ctx, MESSAGES[ctx],
                 signature_file(KEY, sign(KEY, ctx, MESSAGES[ctx])), "valid")
        for ctx in ("manifest", "feed", "keys")
    ]
    good = sign(KEY, "manifest", MANIFEST)
    # Signed over the bare bytes, with no context string in front.
    bare = b64url(private_key(KEY).sign(MANIFEST))
    cases.append(sig_case("no-context-prefix", "manifest", MANIFEST,
                          signature_file(KEY, bare), "bad_signature"))
    # Signed as a feed, checked as a manifest.
    cases.append(sig_case("wrong-context", "manifest", MANIFEST,
                          signature_file(KEY, sign(KEY, "feed", MANIFEST)), "bad_signature"))
    changed = bytearray(MANIFEST)
    changed[-2] ^= 0x01
    cases.append(sig_case("one-byte-changed", "manifest", bytes(changed),
                          signature_file(KEY, good), "bad_signature"))
    cases.append(sig_case("unknown-alg", "manifest", MANIFEST,
                          signature_file(KEY, good, alg="rsa"), "unknown_alg"))
    cases.append(sig_case("bad-base64", "manifest", MANIFEST,
                          signature_file(KEY, "not base64!"), "bad_signature_file"))
    return {"cases": cases}


# File name under vectors/ -> function returning its JSON value.
VECTOR_FILES = {
    "signatures.json": signatures,
}


def render(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv):
    check = "--check" in argv[1:]
    stale = []
    for name, build in VECTOR_FILES.items():
        path = ROOT / "vectors" / name
        text = render(build())
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(name)
        else:
            path.write_text(text)
    for name in stale:
        print(f"FAIL vectors/{name} is missing or out of date; run python scripts/make_vectors.py")
    if check:
        print(f"{len(VECTOR_FILES)} vector files checked, {len(stale)} out of date")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
