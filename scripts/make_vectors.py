#!/usr/bin/env python3
"""Generate the signature, key-set, bundle and feed test vectors, or check they are up to date.

    python scripts/make_vectors.py           write them under vectors/
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
import hashlib
import io
import json
import sys
import warnings
import zipfile
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


def non_canonical(text):
    """The same bytes as the canonical base64url `text`, spelled with a nonzero unused bit."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    unused = {2: 4, 3: 2}[len(text) % 4]  # 43 chars (32 bytes): 2 unused bits; 86 (64 bytes): 4
    last = alphabet.index(text[-1])
    assert last % (1 << unused) == 0
    return text[:-1] + alphabet[last | 1]


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
    # alg is checked before signature is decoded: another algorithm's signature has another length.
    cases.append(sig_case("unknown-alg-other-length", "manifest", MANIFEST,
                          signature_file(KEY, b64url(bytes(256)), alg="rsa"), "unknown_alg"))
    # The right 64 bytes, spelled with a nonzero unused bit: one value, one spelling.
    cases.append(sig_case("non-canonical-signature", "manifest", MANIFEST,
                          signature_file(KEY, non_canonical(good)), "bad_signature_file"))
    return {"cases": cases}


def key_entry(name, created_at, **ends):
    """A key set entry for the test key `name`; `ends` is retired_at and/or revoked_at, or
    overrides any other member (id, alg, public_key)."""
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


def pin(name, **override):
    """A pinned key, as a connection file gives it."""
    publisher, key = name.split("/", 1)
    return dict({"publisher": publisher, "id": key, "alg": "ed25519", "public_key": public_key(name)}, **override)


def signer(name):
    """The signer a reader records: publisher and key id, or None for something unsigned."""
    if name is None:
        return None
    publisher, key = name.split("/", 1)
    return {"publisher": publisher, "key": key}


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

    # A revoked key's public key comes back under a fresh id. The revoked entry keeps its id
    # but is given other bytes, so that no public key is listed twice (that would be
    # bad_key_set, step 1) and only the rollback rule catches it.
    prev = held(key_entry(*K2025, **REVOKED), key_entry(*K2026))
    reborn = key_entry(*K2025, id="2025-06b")
    rebound = key_entry(*K2025, public_key=public_key(K2027[0]), **REVOKED)
    new = key_set(rebound, key_entry(*K2026), reborn, updated_at=HELD_AT)
    add("revoked-key-new-id", prev, [], new, "key_set_rollback")

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
    # A pinned key the new set revokes may not endorse it, stateless or not.
    add("stateless-revokes-own-endorser", None, [pin(K2025[0])], new, "bad_endorsement", signer=K2025[0])
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

    # Endorsement by a key that is no anchor is no endorsement, with a held set too.
    prev = held(key_entry(*K2025))
    new = key_set(key_entry(*K2027), key_entry(*K2025))
    add("unheld-endorser-new-key", prev, [], new, "needs_approval", signer=K2027[0])
    prev = held(key_entry(*K2025), key_entry(*K2026))
    new = key_set(key_entry(*K2025, **RETIRED), key_entry(*K2026))
    add("unheld-endorser-no-new-key", prev, [], new, "accepted", signer=K2027[0])
    # A pinned key is an anchor beside the held set: it endorses a set that adds 2027-03.
    prev = held(key_entry(*K2025))
    new = key_set(key_entry(*K2027), key_entry(*K2026), key_entry(*K2025))
    add("pinned-endorser-with-held-set", prev, [pin(K2026[0])], new, "accepted", signer=K2026[0])
    # The pin for 2026-11 has other bytes than the held set's 2026-11: that id is no anchor.
    prev = held(key_entry(*K2026))
    new = key_set(key_entry(*K2027), key_entry(*K2026))
    add("pin-conflicts-with-held-set", prev, [pin(K2026[0], public_key=public_key(K2027[0]))], new,
        "needs_approval", signer=K2026[0])
    # A held key whose alg changed is new, so it needs an endorsement.
    prev = held(key_entry(*K2026))
    new = key_set(key_entry(*K2026, alg="ml-dsa-44"))
    add("alg-changed-unsigned", prev, [], new, "needs_approval")

    # Refused in step 1, before anything else.
    new = key_set(key_entry(*K2026), key_entry(*K2026, id="2026-11b"))
    add("same-key-two-ids", None, [pin(K2025[0])], new, "bad_key_set")
    new = key_set(key_entry(*K2026, public_key=non_canonical(public_key(K2026[0]))))
    add("non-canonical-public-key", None, [], new, "bad_key_set")
    add("not-json", None, [pin(K2025[0])], None, "bad_key_set", raw_keys=b"not json\n")
    add("not-a-key-set", None, [pin(K2025[0])], {"$type": "org.legiblerecords.keys", "version": 1},
        "bad_key_set")
    # updated_at more than 24 hours after the reader's clock (2026-12-01T00:00:00Z when not given).
    prev = held(key_entry(*K2025))
    new = key_set(key_entry(*K2025, **RETIRED), updated_at="2026-12-02T00:00:01Z")
    add("updated-at-future", prev, [], new, "bad_key_set")
    new = key_set(key_entry(*K2025, **RETIRED), updated_at="2026-12-02T00:00:00Z")
    add("updated-at-24-hours-ahead", prev, [], new, "accepted")
    new = key_set(key_entry(*K2025, **RETIRED))
    add("updated-at-future-of-now", prev, [], new, "bad_key_set", now="2026-11-22T23:59:59Z")

    files = {}
    for name, previous, pins, new, expect, signer_, how in cases:
        stored = how.get("raw_keys") or stored_json(new)
        base = f"key-sets/{name}/"
        case = {"name": name, "previous": previous, "pins": pins, "expect": expect}
        if "now" in how:
            case["now"] = how["now"]
        files[base + "case.json"] = stored_json(case)
        files[base + "keys.json"] = stored
        if "raw_sig" in how:
            files[base + "keys.sig"] = how["raw_sig"]
        elif signer_:
            signed = how.get("signed_bytes", stored)
            files[base + "keys.sig"] = stored_json(signature_file(
                signer_, sign(signer_, how.get("context", "keys"), signed), alg=how.get("alg", "ed25519")))
    return files


BUNDLE_PUBLISHED_AT = "2026-11-24T10:00:00Z"
FEED_ID = "acme.example/track"
STREAM = "policy-acknowledgments"
# Invented record and attachment, shared by every bundle case.
RECORD_PATH = "records/note/welcome.json"
RECORD = stored_json({
    "$type": "example.note",
    "version": 1,
    "title": "Welcome to Acme",
    "body": "Invented text for a test vector.",
})
ATTACHMENT = b"invented attachment bytes\n"
ATTACHMENT_PATH = "files/" + hashlib.sha256(ATTACHMENT).hexdigest()


def bundle_files():
    return {RECORD_PATH: RECORD, ATTACHMENT_PATH: ATTACHMENT}


def bundle_manifest(files, published_at=BUNDLE_PUBLISHED_AT, **extra):
    """manifest.json bytes listing `files` (path -> bytes); the manifest never lists itself."""
    listed = []
    for path in sorted(files):
        entry = {"path": path, "sha256": hashlib.sha256(files[path]).hexdigest()}
        if path.startswith("records/"):
            entry.update(record_type="example.note", record_version=1)
        else:
            entry["media_type"] = "text/plain"
        listed.append(entry)
    manifest = {
        "$type": "org.legiblerecords.bundle",
        "version": 1,
        "files": listed,
        "published_at": published_at,
        "feed": {"id": FEED_ID, "stream": STREAM},
    }
    if published_at is None:
        del manifest["published_at"]
    manifest.update(extra)
    return stored_json(manifest)


def zip_bytes(entries, repeated=()):
    """A zip that is the same bytes on every run: sorted entries, fixed date, deflate.

    `repeated` is a list of (path, bytes) written again after the sorted entries, for a
    zip with two entries of one name.
    """
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z, warnings.catch_warnings():
        warnings.simplefilter("ignore")  # zipfile warns about a repeated name; that is the point
        for path, data in [(p, entries[p]) for p in sorted(entries)] + list(repeated):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            z.writestr(info, data, compresslevel=9)
    return out.getvalue()


def bundle_cases():
    """Directories under vectors/bundles/: case.json and bundle.zip."""
    cases = []

    def add(name, trust, expect, expected_publisher="acme.example", signer=None, mutate=None,
            files=None, published_at=BUNDLE_PUBLISHED_AT, now=None, repeated=()):
        files = dict(files or bundle_files())
        manifest = bundle_manifest(files, published_at)
        sig = signature_file(signer, sign(signer, "manifest", manifest)) if signer else None
        entries = dict(files)
        entries["manifest.json"] = mutate(manifest) if mutate else manifest
        if sig:
            entries["manifest.sig"] = stored_json(sig)
        cases.append((name, trust, expected_publisher, expect, entries, now,
                      [(path, entries[path]) for path in repeated]))

    def trust(*sets, pins=()):
        return {"pins": list(pins), "key_sets": list(sets)}

    active = key_set(key_entry(*K2026))
    verified = {"status": "verified", "publisher": "acme.example", "key": "2026-11"}
    add("signed-active", trust(active), verified, signer=K2026[0])
    # Retired before the bundle was published: still verifies, the key was never compromised.
    retired = key_set(key_entry(*K2026, retired_at="2026-11-24T09:00:00Z"))
    add("signed-retired", trust(retired), verified, signer=K2026[0])
    # Revoked after published_at: a revoked key's dates mean nothing, so it is still refused.
    revoked = key_set(key_entry(*K2026, revoked_at="2026-12-01T00:00:00Z"))
    add("signed-revoked-backdated", trust(revoked), {"error": "revoked_key"}, signer=K2026[0])
    add("unsigned", trust(), {"status": "unverified"}, expected_publisher=None)
    add("unsigned-pinned-publisher", trust(pins=[pin(K2026[0])]),
        {"error": "unsigned_from_pinned_publisher"})
    # manifest.json changed after signing; its file hashes are still right.
    add("tampered-manifest", trust(active), {"error": "bad_signature"}, signer=K2026[0],
        mutate=lambda m: m.replace(b"2026-11-24T10:00:00Z", b"2026-11-24T11:00:00Z"))
    # The attachment changed after the manifest was made and signed.
    entries = bundle_files()
    manifest = bundle_manifest(entries)
    entries[ATTACHMENT_PATH] = ATTACHMENT + b"x"
    cases.append(("tampered-file", trust(active), "acme.example", {"error": "bad_bundle"},
                  dict(entries, **{"manifest.json": manifest,
                                   "manifest.sig": stored_json(signature_file(
                                       K2026[0], sign(K2026[0], "manifest", manifest)))}), None, []))
    # Signed by a key the key set doesn't list.
    add("unknown-key", trust(active), {"error": "unknown_key"}, signer=K2027[0])
    # A file in the zip the manifest doesn't list.
    extra = dict(bundle_files(), **{"records/note/extra.json": RECORD})
    manifest = bundle_manifest(bundle_files())
    cases.append(("extra-unlisted-file", trust(active), "acme.example", {"error": "bad_bundle"},
                  dict(extra, **{"manifest.json": manifest,
                                 "manifest.sig": stored_json(signature_file(
                                     K2026[0], sign(K2026[0], "manifest", manifest)))}), None, []))
    # A valid signature by another publisher's trusted key, on a bundle for acme.example's feed.
    other = key_set(key_entry("other.example/1", "2026-01-01T00:00:00Z"), publisher="other.example")
    add("sig-publisher-mismatch", trust(active, other), {"error": "publisher_mismatch"},
        signer="other.example/1")

    # Two entries named manifest.json, both the same signed manifest: refused by name alone.
    add("duplicate-manifest-entry", trust(active), {"error": "bad_bundle"}, signer=K2026[0],
        repeated=["manifest.json"])
    # The manifest changed after signing and a file changed after the manifest: the signature
    # is checked first.
    entries = bundle_files()
    manifest = bundle_manifest(entries)
    entries[ATTACHMENT_PATH] = ATTACHMENT + b"x"
    entries["manifest.sig"] = stored_json(signature_file(K2026[0], sign(K2026[0], "manifest", manifest)))
    entries["manifest.json"] = manifest.replace(b"2026-11-24T10:00:00Z", b"2026-11-24T11:00:00Z")
    cases.append(("bad-signature-and-file", trust(active), "acme.example", {"error": "bad_signature"},
                  entries, None, []))
    # The key set lists 2026-11 with an alg the reader doesn't know.
    other_alg = key_set(key_entry(*K2026, alg="ml-dsa-44"))
    add("key-unknown-alg", trust(other_alg), {"error": "unknown_alg"}, signer=K2026[0])
    # The pin for 2026-11 has other bytes than the held set's 2026-11: neither is trusted.
    add("pin-conflicts-with-key-set", trust(active, pins=[pin(K2026[0], public_key=public_key(K2027[0]))]),
        {"error": "unknown_key"}, signer=K2026[0])
    # The held set revokes the pinned key's public key under another id.
    revoked_elsewhere = key_set(key_entry(*K2026, id="2026-11-old", revoked_at="2026-11-25T00:00:00Z"))
    add("pin-revoked-under-other-id", trust(revoked_elsewhere, pins=[pin(K2026[0])]),
        {"error": "revoked_key"}, signer=K2026[0])
    # The held set lists the pinned key's public key under another id, not revoked: one key has
    # one name, so the pin doesn't count and a signature naming the pinned id is unknown_key.
    alias = key_set(key_entry(*K2026, id="2026-11-b"))
    add("pin-alias-in-key-set", trust(alias, pins=[pin(K2026[0])]), {"error": "unknown_key"}, signer=K2026[0])
    # Trust comes only from a held key set: an unsigned bundle is still refused.
    add("unsigned-key-set-only", trust(active), {"error": "unsigned_from_pinned_publisher"})
    # published_at more than 24 hours after the reader's clock.
    add("published-at-future", trust(active), {"error": "bad_bundle"}, signer=K2026[0],
        published_at="2026-12-02T00:00:01Z")
    add("published-at-future-of-now", trust(active), {"error": "bad_bundle"}, signer=K2026[0],
        now="2026-11-23T09:59:59Z")

    files = {}
    for name, trust_, expected_publisher, expect, entries, now, repeated in cases:
        base = f"bundles/{name}/"
        case = {"name": name, "trust": trust_, "expected_publisher": expected_publisher, "expect": expect}
        if now is not None:
            case["now"] = now
        files[base + "case.json"] = stored_json(case)
        files[base + "bundle.zip"] = zip_bytes(entries, repeated)
    return files


# Feeds. Every feed case reads acme.example/track, with three streams.
FEED_STREAMS = [STREAM, "access-reviews", "incidents"]
FEED_OLD = "2026-11-24T09:00:00Z"
FEED_HELD = "2026-11-24T10:00:00Z"  # when the reader last accepted the feed and its bundles
FEED_NEW = "2026-11-24T11:00:00Z"
FEED_LATER = "2026-11-24T12:00:00Z"
FEED_URL = "https://feeds.acme.example/track/"


def feed_bundle(stream, published_at, revision=1, feed_id=FEED_ID, signer=K2026[0], tamper=False):
    """`published_at` None leaves it out of the manifest."""
    """A stream's bundle zip: one invented record and the shared attachment, signed for the feed."""
    files = {
        f"records/note/{stream}.json": stored_json({
            "$type": "example.note",
            "version": 1,
            "title": f"Invented note for {stream}",
            "body": f"Invented text for a test vector, revision {revision}.",
        }),
        ATTACHMENT_PATH: ATTACHMENT,
    }
    manifest = bundle_manifest(files, published_at, feed={"id": feed_id, "stream": stream})
    entries = dict(files, **{"manifest.json": manifest})
    if signer:
        entries["manifest.sig"] = stored_json(signature_file(signer, sign(signer, "manifest", manifest)))
    if tamper:
        entries[ATTACHMENT_PATH] = ATTACHMENT + b"x"
    return zip_bytes(entries)


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def feed_connection(pinned=True):
    connection = {
        "$type": "org.legiblerecords.feed-connection",
        "version": 1,
        "feed": FEED_ID,
        "location": {"kind": "https", "url": FEED_URL},
        "auth": {"method": "bearer", "token_env": "ACME_FEED_TOKEN"},
    }
    if pinned:
        connection["keys"] = [dict(pin(K2026[0]), alg="ed25519")]
    return connection


def feed_dir(streams, updated_at, signer=K2026[0], extra=None, contents=None, paths=None, raw_index=None,
             published=None, feed_id=FEED_ID, tamper_index=None):
    """The files at a feed's base URL, as {path: bytes}.

    `streams` is a list of (stream id, bundle zip bytes). `contents` replaces what is
    stored at a bundle's path; `paths` ({position in streams: path}) replaces the
    `bundle` path an entry gives; `published` ({position: published_at}) replaces the
    `published_at` an entry gives (by default its manifest's); `raw_index` replaces
    feed.json's bytes, and is signed like them; `tamper_index` changes feed.json's bytes
    after they are signed; `extra` adds files beside feed.json.
    """
    listed, files = [], {}
    for position, (stream, data) in enumerate(streams):
        digest = sha256_hex(data)
        path = f"bundles/{digest}.zip"
        files[path] = data
        path = (paths or {}).get(position, path)
        published_at = (published or {}).get(position) or json.loads(read_manifest(data))["published_at"]
        listed.append({
            "id": stream,
            "title": f"Invented stream {stream}",
            "record_types": ["example.note"],
            "bundle": path,
            "sha256": digest,
            "published_at": published_at,
        })
    files.update(contents or {})
    index = stored_json({
        "$type": "org.legiblerecords.feed",
        "version": 1,
        "id": feed_id,
        "publisher": "acme.example",
        "audience": "Monorail, for Track",
        "updated_at": updated_at,
        "streams": listed,
    })
    if raw_index is not None:
        index = raw_index
    files["feed.json"] = index
    if signer:
        files["feed.sig"] = stored_json(signature_file(signer, sign(signer, "feed", index)))
    if tamper_index:
        files["feed.json"] = tamper_index(index)
    files.update(extra or {})
    return files


def read_manifest(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read("manifest.json")


def bundle_signer(data):
    """The signer a reader records for a bundle zip, or None when it is unsigned."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if "manifest.sig" not in z.namelist():
            return None
        sig = json.loads(z.read("manifest.sig"))
    return {"publisher": sig["publisher"], "key": sig["key"]}


def reader_state(bundles, updated_at=FEED_HELD, feed_signer=K2026[0], held_keys=None, approved=()):
    """What a reader holds after accepting `bundles` ({stream: zip bytes}) in a feed at
    `updated_at`, signed by `feed_signer`; `held_keys` is the acme.example key set it holds."""
    return {
        "feed_updated_at": updated_at,
        "feed_signer": signer(feed_signer),
        "streams": {
            stream: {
                "sha256": sha256_hex(data),
                "published_at": json.loads(read_manifest(data))["published_at"],
                "signer": bundle_signer(data),
            }
            for stream, data in bundles.items()
        },
        "key_sets": {"acme.example": held_keys or key_set(key_entry(*K2026))},
        "approved": list(approved),
    }


def cleared_stream(published_at):
    """A stream a revocation cleared: no sha256 or signer, and its published_at kept as a floor."""
    return {"sha256": None, "published_at": published_at, "signer": None}


def served_keys(new, signer_=None):
    """The key-set/ files a publisher serves: keys.json, and keys.sig when `signer_` endorses it."""
    stored = stored_json(new)
    files = {"keys.json": stored}
    if signer_:
        files["keys.sig"] = stored_json(signature_file(signer_, sign(signer_, "keys", stored)))
    return files


def feed_cases():
    """Directories under vectors/feeds/: case.json, and feed/ with the files at the feed's base URL."""
    s0, s1, s2 = FEED_STREAMS
    held = {s: feed_bundle(s, FEED_HELD) for s in FEED_STREAMS}
    newer = {s: feed_bundle(s, FEED_NEW, revision=2) for s in FEED_STREAMS}
    current = list(held.items())
    cases = []

    def add(name, state, files, index, streams, connection=None, keys=None, key_set_=None, now=None,
            after=None):
        """`keys` is the key-set/ files the publisher serves, and `key_set_` what the reader makes of them;
        `after`, when given, is the reader state the poll must leave."""
        expect = {"index": index, "streams": streams}
        if keys is not None:
            expect["key_set"] = key_set_
        if after is not None:
            expect["state"] = after
        cases.append((name, state, files, expect, connection or feed_connection(), keys or {}, now))

    def every(outcome, **others):
        return dict({s: outcome for s in FEED_STREAMS}, **others)

    add("first-read", None, feed_dir(current, FEED_NEW), "ok", every("accepted"))
    add("unchanged", reader_state(held), feed_dir(current, FEED_HELD), "ok", every("unchanged"))
    add("one-changed", reader_state(held), feed_dir([(s0, newer[s0])] + current[1:], FEED_NEW),
        "ok", every("unchanged", **{s0: "accepted"}))
    add("withdrawn", reader_state(held), feed_dir(current[:2], FEED_NEW),
        "ok", every("unchanged", **{s2: "withdrawn"}))
    add("stale-index", reader_state(held), feed_dir(current, FEED_OLD), "stale_feed", {})
    # The reader holds the newer bundle; the feed offers the older signed one again.
    state = reader_state(dict(held, **{s0: newer[s0]}), updated_at=FEED_NEW)
    add("replay", state, feed_dir(current, FEED_LATER), "ok", every("unchanged", **{s0: "replay"}))
    # Different bytes, published at the same instant as the held bundle, written with another offset.
    same_instant = feed_bundle(s0, "2026-11-24T11:00:00+01:00", revision=2)
    add("equal-published-at", reader_state(held), feed_dir([(s0, same_instant)] + current[1:], FEED_NEW),
        "ok", every("unchanged", **{s0: "replay"}))
    add("swapped-streams", reader_state(held),
        feed_dir([(s0, newer[s1]), (s1, newer[s0]), (s2, held[s2])], FEED_NEW),
        "ok", every("unchanged", **{s0: "wrong_stream", s1: "wrong_stream"}))
    other = feed_bundle(s0, FEED_HELD, feed_id="acme.example/other")
    add("other-feed", None, feed_dir([(s0, other)] + current[1:], FEED_NEW),
        "ok", every("accepted", **{s0: "wrong_feed"}))
    # bundles/<sha256 of held[s0]>.zip holds other bytes.
    add("download-mismatch", None,
        feed_dir(current, FEED_NEW, contents={f"bundles/{sha256_hex(held[s0])}.zip": newer[s0]}),
        "ok", every("accepted", **{s0: "download_mismatch"}))
    add("unsigned-index-pinned", None, feed_dir(current, FEED_NEW, signer=None),
        "unsigned_from_pinned_publisher", {})
    # Refused before anything is decrypted, so an empty feed.json.age is enough.
    add("plain-and-encrypted", None, feed_dir(current, FEED_NEW, extra={"feed.json.age": b""}),
        "plain_and_encrypted", {})
    # A stateless reader can't tell an old bundle from a new one; it passes published_at on.
    old = feed_bundle(s0, FEED_OLD, revision=0)
    add("stateless-replay", None, feed_dir([(s0, old)] + current[1:], FEED_NEW), "ok", every("accepted"))
    bad = feed_bundle(s0, FEED_HELD, tamper=True)
    add("one-stream-bad-others-fine", None, feed_dir([(s0, bad)] + current[1:], FEED_NEW),
        "ok", every("accepted", **{s0: "bad_bundle"}))

    # Trust comes only from the key set the reader holds: the connection pins nothing.
    add("unsigned-index-key-set", reader_state(held), feed_dir(current, FEED_NEW, signer=None),
        "unsigned_from_pinned_publisher", {}, connection=feed_connection(pinned=False))
    # Signed, so the signature passes and the index is refused for what it holds.
    add("index-not-json", None, feed_dir(current, FEED_NEW, raw_index=b"not json\n"), "bad_feed", {})
    add("repeated-stream-id", None, feed_dir(current + [(s0, newer[s0])], FEED_NEW), "bad_feed", {})
    # The entry's sha256 is held[s0]'s, but its path names held[s1]'s file.
    add("bundle-path-mismatch", None,
        feed_dir(current, FEED_NEW, paths={0: f"bundles/{sha256_hex(held[s1])}.zip"}), "bad_feed", {})

    # The index and its signature, each case one defect.
    add("index-tampered", None,
        feed_dir(current, FEED_NEW, tamper_index=lambda b: b.replace(b"Monorail, for Track", b"Monorail, for Trace")),
        "bad_signature", {})
    revoked_2025 = key_set(key_entry(*K2026), key_entry(*K2025, **REVOKED), updated_at=HELD_AT)
    add("index-signed-by-revoked", reader_state(held, held_keys=revoked_2025),
        feed_dir(current, FEED_NEW, signer=K2025[0]), "revoked_key", {})
    # Signed by a key of another publisher that the reader doesn't trust: the publisher is
    # checked before the key is looked up.
    add("index-other-publisher", None, feed_dir(current, FEED_NEW, signer="other.example/1"),
        "publisher_mismatch", {})
    add("index-unknown-key", None, feed_dir(current, FEED_NEW, signer=K2027[0]), "unknown_key", {})
    add("index-wrong-id", None, feed_dir(current, FEED_NEW, feed_id="acme.example/other"), "wrong_feed", {})
    add("plain-feed-lists-zip-age", None,
        feed_dir(current, FEED_NEW, paths={0: f"bundles/{sha256_hex(held[s0])}.zip.age"}), "bad_feed", {})
    # The index is dated more than 24 hours after the reader's clock.
    add("index-future-updated-at", None, feed_dir(current, FEED_NEW), "bad_feed", {},
        now="2026-11-23T10:59:59Z")

    # One stream, one defect.
    no_date = feed_bundle(s0, None)
    add("bundle-missing-published-at", None,
        feed_dir([(s0, no_date)] + current[1:], FEED_NEW, published={0: FEED_HELD}),
        "ok", every("accepted", **{s0: "missing_published_at"}))
    # Unsigned throughout, from a publisher the reader doesn't trust: published_at is still required.
    unsigned_feed = [(s0, feed_bundle(s0, None, signer=None))] + [
        (s, feed_bundle(s, FEED_HELD, signer=None)) for s in (s1, s2)]
    add("unsigned-bundle-missing-published-at", None,
        feed_dir(unsigned_feed, FEED_NEW, signer=None, published={0: FEED_HELD}),
        "ok", every("accepted", **{s0: "missing_published_at"}), connection=feed_connection(pinned=False))
    unsigned = feed_bundle(s0, FEED_NEW, revision=2, signer=None)
    add("unsigned-bundle-pinned", None, feed_dir([(s0, unsigned)] + current[1:], FEED_NEW),
        "ok", every("accepted", **{s0: "unsigned_from_pinned_publisher"}))
    add("unsigned-bundle-key-set-only", reader_state(held), feed_dir([(s0, unsigned)] + current[1:], FEED_NEW),
        "ok", every("unchanged", **{s0: "unsigned_from_pinned_publisher"}), connection=feed_connection(pinned=False))
    add("published-at-mismatch", None, feed_dir(current, FEED_NEW, published={0: FEED_NEW}),
        "ok", every("accepted", **{s0: "bad_bundle"}))
    future = feed_bundle(s0, "2026-12-02T00:00:01Z")
    add("bundle-future-published-at", None, feed_dir([(s0, future)] + current[1:], FEED_NEW),
        "ok", every("accepted", **{s0: "bad_bundle"}))

    # The key set the publisher serves on this poll.
    with_2027 = key_set(key_entry(*K2027), key_entry(*K2026))
    add("key-set-rotation-used-at-once", None, feed_dir(current, FEED_NEW, signer=K2027[0]),
        "ok", every("accepted"), keys=served_keys(with_2027, K2026[0]), key_set_="accepted")
    add("key-set-pending-key-unknown", None, feed_dir(current, FEED_NEW, signer=K2027[0]),
        "unknown_key", {}, keys=served_keys(with_2027), key_set_="needs_approval")
    approved = [dict(pin(K2027[0]))]
    add("key-set-approved-key", reader_state(held, approved=approved), feed_dir(current, FEED_NEW, signer=K2027[0]),
        "ok", every("unchanged"), keys=served_keys(with_2027), key_set_="accepted")
    add("key-set-other-publisher", None, feed_dir(current, FEED_NEW),
        "ok", every("accepted"),
        keys=served_keys(key_set(key_entry("other.example/1", "2026-01-01T00:00:00Z"), publisher="other.example")),
        key_set_="bad_key_set")
    add("key-set-future-updated-at", None, feed_dir(current, FEED_NEW),
        "ok", every("accepted"),
        keys=served_keys(key_set(key_entry(*K2026), updated_at="2026-12-02T00:00:01Z")), key_set_="bad_key_set")
    # The connection pins nothing and the reader holds nothing, but the publisher serves a
    # key set: it signs, so an unsigned index from it is refused.
    add("unsigned-index-served-key-set", None, feed_dir(current, FEED_NEW, signer=None),
        "unsigned_from_pinned_publisher", {}, connection=feed_connection(pinned=False),
        keys=served_keys(key_set(key_entry(*K2026))), key_set_="needs_approval")
    # A set waiting for approval still revokes: the pinned 2025-06 signed the index.
    pins_2025_2026 = dict(feed_connection(), keys=[pin(K2025[0]), pin(K2026[0])])
    add("pending-set-revokes-pin", None, feed_dir(current, FEED_NEW, signer=K2025[0]),
        "revoked_key", {}, connection=pins_2025_2026,
        keys=served_keys(key_set(key_entry(*K2027), key_entry(*K2026), key_entry(*K2025, **REVOKED))),
        key_set_="needs_approval")

    # A revocation in the held set (one accepted on this poll included) clears what the key
    # signed: the stream's sha256 and signer go, so it is fetched again next poll, and its
    # published_at stays as the replay floor.
    both = key_set(key_entry(*K2026), key_entry(*K2025), updated_at=HELD_AT)
    revokes_2025 = key_set(key_entry(*K2026), key_entry(*K2025, **REVOKED))
    by_2025 = dict(held, **{s0: feed_bundle(s0, FEED_HELD, signer=K2025[0])})
    cleared = cleared_stream(FEED_HELD)
    after = reader_state(by_2025, updated_at=FEED_NEW, held_keys=revokes_2025)
    after["streams"][s0] = cleared
    add("revoked-key-clears-stream", reader_state(by_2025, held_keys=both),
        feed_dir(list(by_2025.items()), FEED_NEW),
        "ok", every("unchanged", **{s0: "revoked_key"}), keys=served_keys(revokes_2025), key_set_="accepted",
        after=after)
    # The same, and the index is then refused: the stream is still cleared.
    after = reader_state(by_2025, held_keys=revokes_2025)
    after["streams"][s0] = cleared
    add("revoked-key-index-refused", reader_state(by_2025, held_keys=both),
        feed_dir(list(by_2025.items()), FEED_NEW, signer=None),
        "unsigned_from_pinned_publisher", {s0: "revoked_key"}, keys=served_keys(revokes_2025), key_set_="accepted",
        after=after)
    # The thief of 2025-06 signed an index dated ahead. Revoking 2025-06 clears the index's
    # signer but keeps its updated_at: a floor at most 24 hours ahead, never a reopened replay.
    ahead = "2026-12-01T12:00:00Z"
    after = reader_state(held, updated_at=ahead, feed_signer=None, held_keys=revokes_2025)
    add("revoked-key-keeps-watermark",
        reader_state(held, updated_at=ahead, feed_signer=K2025[0], held_keys=both),
        feed_dir(current, FEED_NEW), "stale_feed", {}, keys=served_keys(revokes_2025), key_set_="accepted",
        after=after)
    # A stream cleared by a revocation is later offered an older bundle, signed by a key that
    # is still trusted: the kept published_at refuses it.
    state = reader_state(held, held_keys=revoked_2025)
    state["streams"][s0] = cleared
    older = feed_bundle(s0, FEED_OLD, revision=0)
    add("revoked-stream-older-bundle", state, feed_dir([(s0, older)] + current[1:], FEED_NEW),
        "ok", every("unchanged", **{s0: "replay"}))

    # A revocation in a served set the reader doesn't hold refuses what the key signed on this
    # poll, and changes nothing the reader keeps. Whoever controls the server can serve such a
    # set with no key; if it cleared the floors, the next poll could replay old signed content.
    state = reader_state(held)
    revokes_2026 = key_set(key_entry(*K2027), key_entry(*K2026, **REVOKED))
    add("pending-set-revokes-signer", state, feed_dir(current, FEED_HELD),
        "revoked_key", {}, keys=served_keys(revokes_2026), key_set_="needs_approval", after=state)
    # The next poll: the genuine key set again, with an older index and bundles that 2026-11
    # really signed. The watermark is still there.
    old_feed = [(s, feed_bundle(s, FEED_OLD, revision=0)) for s in FEED_STREAMS]
    add("pending-set-revokes-signer-next-poll", state, feed_dir(old_feed, FEED_OLD),
        "stale_feed", {}, keys=served_keys(key_set(key_entry(*K2026))), key_set_="accepted", after=state)
    # The same revocation in a set refused as key_set_rollback (older than the held set) ...
    add("rollback-set-revokes-signer", state, feed_dir(current, FEED_HELD),
        "revoked_key", {}, keys=served_keys(key_set(key_entry(*K2026, **REVOKED), updated_at=HELD_AT)),
        key_set_="key_set_rollback", after=state)
    # ... and in one refused as bad_endorsement (2026-11 may not endorse a set that revokes it).
    add("bad-endorsement-set-revokes-signer", state, feed_dir(current, FEED_HELD),
        "revoked_key", {}, keys=served_keys(revokes_2026, K2026[0]), key_set_="bad_endorsement", after=state)

    # The connection pins 2026-11's public key as 2026-11; the publisher's key set lists the
    # same bytes as 2026-11-b. One key has one name, so the pin doesn't count and an index
    # signed naming 2026-11 is unknown_key: whether the reader holds that set ...
    alias = key_set(key_entry(*K2026, id="2026-11-b"))
    state = reader_state(held, held_keys=alias)
    add("pin-alias-held-set", state, feed_dir(current, FEED_NEW), "unknown_key", {}, after=state)
    # ... or is served it on this poll, by a stateless reader, waiting for approval.
    add("pin-alias-served-set", None, feed_dir(current, FEED_NEW), "unknown_key", {},
        keys=served_keys(alias), key_set_="needs_approval")

    files = {}
    for name, state, feed_files, expect, connection, keys, now in cases:
        base = f"feeds/{name}/"
        case = {"name": name, "connection": connection, "state": state, "expect": expect}
        if now is not None:
            case["now"] = now
        files[base + "case.json"] = stored_json(case)
        for path, data in feed_files.items():
            files[base + "feed/" + path] = data
        for path, data in keys.items():
            files[base + "key-set/" + path] = data
    return files


# File name under vectors/ -> function returning its JSON value.
VECTOR_FILES = {
    "signatures.json": signatures,
}

# Functions returning {path under vectors/: bytes} for vectors kept as directories.
VECTOR_TREES = [key_set_cases, bundle_cases, feed_cases]


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
