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
    "acme.example/2027-03": bytes(range(128, 160)),
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


def key_entry(name, created_at, **ends):
    """A key set entry for the test key `name`; `ends` is retired_at and/or revoked_at."""
    entry = {
        "id": name.split("/", 1)[1],
        "alg": "ed25519",
        "public_key": public_key(name),
        "created_at": created_at,
    }
    entry.update(ends)
    return entry


HELD_AT = "2026-06-02T00:00:00Z"  # updated_at of a previous key set
NEW_AT = "2026-11-24T00:00:00Z"  # updated_at of the key set a case is about


def key_set(*entries, publisher="acme.example", updated_at=NEW_AT):
    return {
        "$type": "org.legiblerecords.keys",
        "version": 1,
        "publisher": publisher,
        "updated_at": updated_at,
        "keys": list(entries),
    }


def pin(name):
    publisher, key = name.split("/", 1)
    return {"publisher": publisher, "id": key, "public_key": public_key(name)}


K2024 = ("acme.example/2024-01", "2024-01-01T00:00:00Z")
K2025 = ("acme.example/2025-06", "2025-06-01T00:00:00Z")
K2026 = ("acme.example/2026-11", "2026-11-24T00:00:00Z")
K2027 = ("acme.example/2027-03", "2027-03-01T00:00:00Z")
RETIRED_2026 = {"retired_at": "2027-03-01T00:00:00Z"}
RETIRED = {"retired_at": "2026-11-24T00:00:00Z"}
REVOKED = {"revoked_at": "2026-06-01T00:00:00Z"}


def key_set_cases():
    """Directories under vectors/key-sets/: case.json, keys.json, and keys.sig when signed."""
    cases = []

    def add(name, previous, pins, new, expect, signer=None, **how):
        cases.append((name, previous, pins, new, expect, signer, how))

    def held(*entries, updated_at=HELD_AT):
        return key_set(*entries, updated_at=updated_at)

    # The endorser is active in the previous set; the new set retires it and adds 2026-11.
    prev = held(key_entry(*K2025))
    new = key_set(key_entry(*K2026), key_entry(*K2025, **RETIRED))
    add("endorsed-by-active", prev, [], new, "accepted", signer=K2025[0])
    # The endorser was already retired in the previous set.
    prev = held(key_entry(*K2025, **RETIRED), key_entry(*K2026))
    new = key_set(key_entry(*K2027), key_entry(*K2026), key_entry(*K2025, **RETIRED))
    add("endorsed-by-retired", prev, [], new, "bad_endorsement", signer=K2025[0])
    # The endorser was already revoked in the previous set.
    prev = held(key_entry(*K2025, **REVOKED), key_entry(*K2026))
    new = key_set(key_entry(*K2027), key_entry(*K2026), key_entry(*K2025, **REVOKED))
    add("endorsed-by-revoked", prev, [], new, "bad_endorsement", signer=K2025[0])
    # A key is added and nothing endorses it.
    prev = held(key_entry(*K2025))
    new = key_set(key_entry(*K2026), key_entry(*K2025))
    add("new-key-unsigned", prev, [], new, "needs_approval")
    # Only an end date is added, so nothing needs approval.
    prev = held(key_entry(*K2025), key_entry(*K2026))
    new = key_set(key_entry(*K2025, **RETIRED), key_entry(*K2026))
    add("no-new-key-unsigned", prev, [], new, "accepted")
    # No previous set: the endorser is pinned, and the new set doesn't revoke it.
    new = key_set(key_entry(*K2026), key_entry(*K2025, **RETIRED))
    add("stateless-endorsed-by-pin", None, [pin(K2025[0])], new, "accepted", signer=K2025[0])
    # No previous set: the endorser is a key the reader has no pin for.
    new = key_set(key_entry(*K2027), key_entry(*K2026, **RETIRED_2026), key_entry(*K2025, **RETIRED))
    add("stateless-second-rotation", None, [pin(K2025[0])], new, "needs_approval", signer=K2026[0])
    # Signed with the manifest context instead of the keys context.
    prev = held(key_entry(*K2025))
    new = key_set(key_entry(*K2026), key_entry(*K2025, **RETIRED))
    add("endorsement-wrong-context", prev, [], new, "bad_endorsement",
        signer=K2025[0], context="manifest")

    # Rollback: refused before any endorsement is looked at.
    prev = held(key_entry(*K2025, **REVOKED), key_entry(*K2026))
    new = key_set(key_entry(*K2025), key_entry(*K2026))
    add("unsigned-clears-revoked", prev, [], new, "key_set_rollback")
    prev = held(key_entry(*K2025, **RETIRED), key_entry(*K2026))
    new = key_set(key_entry(*K2025), key_entry(*K2026))
    add("unsigned-clears-retired", prev, [], new, "key_set_rollback")
    # Validly endorsed, but older than the set the reader holds.
    prev = held(key_entry(*K2025), updated_at="2026-11-24T00:00:00Z")
    new = key_set(key_entry(*K2026), key_entry(*K2025, **RETIRED), updated_at="2026-06-01T00:00:00Z")
    add("signed-old-updated-at", prev, [], new, "key_set_rollback", signer=K2025[0])
    prev = held(key_entry(*K2025), key_entry(*K2026))
    new = key_set(key_entry(*K2026))
    add("drops-held-key", prev, [], new, "key_set_rollback")

    # A key id listed twice: the reader refuses the set, whichever entry it would have read.
    prev = held(key_entry(*K2025, **REVOKED), key_entry(*K2026))
    new = key_set(key_entry(*K2025), key_entry(*K2025, **REVOKED), key_entry(*K2026),
                  updated_at=HELD_AT)
    add("duplicate-id-unrevokes", prev, [], new, "bad_key_set")
    add("duplicate-id-stateless", None, [pin(K2025[0])], new, "bad_key_set")

    # updated_at is compared as an instant: 09:30 at -02:00 is later than 10:00Z, though
    # it sorts earlier as text.
    prev = held(key_entry(*K2025), updated_at="2026-11-24T10:00:00Z")
    new = key_set(key_entry(*K2026), key_entry(*K2025, **RETIRED), updated_at="2026-11-24T09:30:00-02:00")
    add("updated-at-with-offset", prev, [], new, "accepted", signer=K2025[0])

    # More endorsement cases.
    prev = held(key_entry(*K2025))
    new = key_set(key_entry(*K2026), key_entry(*K2025, **REVOKED))
    add("revokes-own-endorser", prev, [], new, "bad_endorsement", signer=K2025[0])
    add("stateless-revokes-own-endorser", None, [pin(K2025[0])], new, "needs_approval", signer=K2025[0])
    new = key_set(key_entry(*K2026), key_entry(*K2025, **RETIRED))
    add("pinned-endorser-bad-signature", None, [pin(K2025[0])], new, "bad_endorsement",
        signer=K2025[0], signed_bytes=b"not the key set")
    # Nothing is new, so an endorsement nobody can check changes nothing.
    new = key_set(key_entry(*K2025))
    add("stateless-unpinned-endorser-no-new-key", None, [pin(K2025[0])], new, "accepted",
        signer=K2026[0])
    prev = held(key_entry(*K2025))
    new = key_set(key_entry(*K2026), key_entry(*K2025, **RETIRED))
    add("endorsement-other-publisher", prev, [], new, "bad_endorsement", signer="other.example/1")
    add("endorsement-unknown-alg", prev, [], new, "bad_endorsement", signer=K2025[0], alg="rsa")
    add("endorsement-unparseable", prev, [], new, "bad_endorsement", raw_sig=b"not json\n")

    files = {}
    for name, previous, pins, new, expect, signer, how in cases:
        stored = stored_json(new)
        base = f"key-sets/{name}/"
        files[base + "case.json"] = stored_json(
            {"name": name, "previous": previous, "pins": pins, "expect": expect})
        files[base + "keys.json"] = stored
        if "raw_sig" in how:
            files[base + "keys.sig"] = how["raw_sig"]
        elif signer:
            signed = how.get("signed_bytes", stored)
            files[base + "keys.sig"] = stored_json(signature_file(
                signer, sign(signer, how.get("context", "keys"), signed), alg=how.get("alg", "ed25519")))
    return files


# File name under vectors/ -> function returning its JSON value.
VECTOR_FILES = {
    "signatures.json": signatures,
}

# Functions returning {path under vectors/: bytes} for vectors kept as directories.
VECTOR_TREES = [key_set_cases]


def render(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def expected_files():
    """Every generated file: path under vectors/ -> bytes."""
    files = {name: render(build()).encode("utf-8") for name, build in VECTOR_FILES.items()}
    for tree in VECTOR_TREES:
        files.update(tree())
    return files


def main(argv):
    check = "--check" in argv[1:]
    files = expected_files()
    stale = []
    for name, data in files.items():
        path = ROOT / "vectors" / name
        if check:
            if not path.exists() or path.read_bytes() != data:
                stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if check:
        # A generated directory must hold nothing that isn't generated.
        for tree in sorted({n.split("/", 1)[0] for n in files if "/" in n}):
            for path in sorted((ROOT / "vectors" / tree).rglob("*")):
                rel = path.relative_to(ROOT / "vectors").as_posix()
                if path.is_file() and rel not in files:
                    stale.append(rel)
    for name in stale:
        print(f"FAIL vectors/{name} is missing, out of date or not generated; run python scripts/make_vectors.py")
    if check:
        print(f"{len(files)} vector files checked, {len(stale)} out of date")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
