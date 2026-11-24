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

    # A revoked key's public key comes back under a fresh id.
    prev = held(key_entry(*K2025, **REVOKED), key_entry(*K2026))
    reborn = dict(key_entry(*K2025), id="2025-06b")
    new = key_set(key_entry(*K2025, **REVOKED), key_entry(*K2026), reborn, updated_at=HELD_AT)
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
    manifest.update(extra)
    return stored_json(manifest)


def zip_bytes(entries):
    """A zip that is the same bytes on every run: sorted entries, fixed date, deflate."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for path in sorted(entries):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            z.writestr(info, entries[path], compresslevel=9)
    return out.getvalue()


def bundle_cases():
    """Directories under vectors/bundles/: case.json and bundle.zip."""
    cases = []

    def add(name, trust, expect, expected_publisher="acme.example", signer=None, mutate=None,
            files=None, sig_override=None):
        files = dict(files or bundle_files())
        manifest = bundle_manifest(files)
        sig = signature_file(signer, sign(signer, "manifest", manifest)) if signer else None
        entries = dict(files)
        entries["manifest.json"] = mutate(manifest) if mutate else manifest
        if sig:
            entries["manifest.sig"] = stored_json(sig)
        cases.append((name, trust, expected_publisher, expect, entries))

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
                                       K2026[0], sign(K2026[0], "manifest", manifest)))})))
    # Signed by a key the key set doesn't list.
    add("unknown-key", trust(active), {"error": "unknown_key"}, signer=K2027[0])
    # A file in the zip the manifest doesn't list.
    extra = dict(bundle_files(), **{"records/note/extra.json": RECORD})
    manifest = bundle_manifest(bundle_files())
    cases.append(("extra-unlisted-file", trust(active), "acme.example", {"error": "bad_bundle"},
                  dict(extra, **{"manifest.json": manifest,
                                 "manifest.sig": stored_json(signature_file(
                                     K2026[0], sign(K2026[0], "manifest", manifest)))})))
    # A valid signature by another publisher's trusted key, on a bundle for acme.example's feed.
    other = key_set(key_entry("other.example/1", "2026-01-01T00:00:00Z"), publisher="other.example")
    add("sig-publisher-mismatch", trust(active, other), {"error": "publisher_mismatch"},
        signer="other.example/1")

    files = {}
    for name, trust_, expected_publisher, expect, entries in cases:
        base = f"bundles/{name}/"
        files[base + "case.json"] = stored_json({
            "name": name, "trust": trust_,
            "expected_publisher": expected_publisher, "expect": expect})
        files[base + "bundle.zip"] = zip_bytes(entries)
    return files


# Feeds. Every feed case reads acme.example/track, with three streams.
FEED_STREAMS = [STREAM, "access-reviews", "incidents"]
FEED_OLD = "2026-11-24T09:00:00Z"
FEED_HELD = "2026-11-24T10:00:00Z"  # when the reader last accepted the feed and its bundles
FEED_NEW = "2026-11-24T11:00:00Z"
FEED_LATER = "2026-11-24T12:00:00Z"
FEED_URL = "https://feeds.acme.example/track/"


def feed_bundle(stream, published_at, revision=1, feed_id=FEED_ID, signer=K2026[0], tamper=False):
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


def feed_dir(streams, updated_at, signer=K2026[0], extra=None, contents=None, paths=None, raw_index=None):
    """The files at a feed's base URL, as {path: bytes}.

    `streams` is a list of (stream id, bundle zip bytes). `contents` replaces what is
    stored at a bundle's path; `paths` ({position in streams: path}) replaces the
    `bundle` path an entry gives; `raw_index` replaces feed.json's bytes, and is signed
    like them; `extra` adds files beside feed.json.
    """
    listed, files = [], {}
    for position, (stream, data) in enumerate(streams):
        digest = sha256_hex(data)
        path = f"bundles/{digest}.zip"
        files[path] = data
        path = (paths or {}).get(position, path)
        published_at = json.loads(read_manifest(data))["published_at"]
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
        "id": FEED_ID,
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
    files.update(extra or {})
    return files


def read_manifest(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read("manifest.json")


def reader_state(bundles, updated_at=FEED_HELD):
    """What a reader holds after accepting `bundles` ({stream: zip bytes}) in a feed at `updated_at`."""
    return {
        "feed_updated_at": updated_at,
        "streams": {
            stream: {
                "sha256": sha256_hex(data),
                "published_at": json.loads(read_manifest(data))["published_at"],
            }
            for stream, data in bundles.items()
        },
        "key_sets": {"acme.example": key_set(key_entry(*K2026))},
        "approved": [],
    }


def feed_cases():
    """Directories under vectors/feeds/: case.json, and feed/ with the files at the feed's base URL."""
    s0, s1, s2 = FEED_STREAMS
    held = {s: feed_bundle(s, FEED_HELD) for s in FEED_STREAMS}
    newer = {s: feed_bundle(s, FEED_NEW, revision=2) for s in FEED_STREAMS}
    current = list(held.items())
    cases = []

    def add(name, state, files, index, streams, connection=None):
        cases.append((name, state, files, {"index": index, "streams": streams},
                      connection or feed_connection()))

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

    files = {}
    for name, state, feed_files, expect, connection in cases:
        base = f"feeds/{name}/"
        files[base + "case.json"] = stored_json({
            "name": name, "connection": connection, "state": state, "expect": expect})
        for path, data in feed_files.items():
            files[base + "feed/" + path] = data
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
