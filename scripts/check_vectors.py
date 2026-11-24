#!/usr/bin/env python3
"""Check that the test vectors are well formed.

This doesn't run an implementation: it checks the vectors themselves, so a
mistake in them is caught before an implementation is tested against it.

- every case has a unique name and the keys its kind needs;
- every expected body is a valid JSON Schema 2020-12 schema;
- every restricted-YAML case expects either a value or a known error.

- every key-set case, re-checked under rules written here, gives its expected outcome;
- every bundle case, opened as a zip and re-checked here (manifest hashes, file list,
  signature, trust), gives its expected outcome;
- every feed case, re-checked here in the order of spec/feeds.md § Reading a feed
  (reusing the bundle and signature re-checks), gives its expected index and stream
  outcomes (an index that isn't a valid feed is bad_feed), and its connection is a
  valid record;
- every outcome code a vector expects is in the table in spec/feeds.md § Outcomes;
- every signature case verifies, or fails with its expected code, under a
  re-check written here rather than imported from make_vectors.py.

Needs: pip install jsonschema cryptography
"""

import base64
import binascii
import hashlib
import io
from datetime import datetime
import json
import re
import sys
import zipfile
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from check_fixtures import load_registry

ROOT = Path(__file__).resolve().parent.parent
YAML_ERRORS = {
    "too_large", "too_deep", "multiple_documents", "anchor", "alias", "tag",
    "non_string_key", "duplicate_key", "syntax", "number_range",
}
SIGNATURE_CONTEXTS = {
    "manifest": b"legible-records/v1 manifest\n",
    "feed": b"legible-records/v1 feed\n",
    "keys": b"legible-records/v1 keys\n",
}
B64URL = re.compile(r"^[A-Za-z0-9_-]*$")
OPTIONS = {"base", "common", "location"}


def outcome_codes():
    """The codes in the table under "## Outcomes" in spec/feeds.md, or None if it has none."""
    try:
        text = (ROOT / "spec" / "feeds.md").read_text()
    except OSError:
        return None
    match = re.search(r"^## Outcomes\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        return None
    codes = set()
    for row in re.findall(r"^\|([^|]*)\|", match.group(1), re.M):
        codes.update(re.findall(r"`([a-z_]+)`", row))
    return codes or None


def check_schema_language(path, problems):
    data = json.loads(path.read_text())
    names = set()
    for i, case in enumerate(data["cases"]):
        where = f"{path.name} case {i} ({case.get('name')})"
        name = case.get("name")
        if not name or name in names:
            problems.append(f"{where}: missing or duplicate name")
        names.add(name)
        if not isinstance(case.get("schema"), str):
            problems.append(f"{where}: no schema name")
        unknown = set(case.get("options", {})) - OPTIONS
        if unknown:
            problems.append(f"{where}: unknown options {sorted(unknown)}")
        expect = case.get("expect", {})
        if "short" in case:
            if set(expect) not in ({"body"}, {"problems"}):
                problems.append(f"{where}: an expansion case expects exactly body or problems")
            if "body" in expect:
                try:
                    Draft202012Validator.check_schema(expect["body"])
                except SchemaError as err:
                    problems.append(f"{where}: expected body isn't a valid schema: {err.message}")
            for p in expect.get("problems", []):
                if set(p) != {"line", "path", "message"}:
                    problems.append(f"{where}: a problem needs line, path and message")
        elif "body" in case:
            if set(expect) != {"short"}:
                problems.append(f"{where}: a generation case expects short")
            try:
                Draft202012Validator.check_schema(case["body"])
            except SchemaError as err:
                problems.append(f"{where}: input body isn't a valid schema: {err.message}")
        else:
            problems.append(f"{where}: neither short nor body")
    return len(data["cases"])


def check_restricted_yaml(path, problems):
    data = json.loads(path.read_text())
    names = set()
    for i, case in enumerate(data["cases"]):
        where = f"{path.name} case {i} ({case.get('name')})"
        if case.get("name") in names:
            problems.append(f"{where}: duplicate name")
        names.add(case.get("name"))
        if not isinstance(case.get("yaml"), str):
            problems.append(f"{where}: no yaml")
        expect = case.get("expect", {})
        if set(expect) == {"error"}:
            if expect["error"] not in YAML_ERRORS:
                problems.append(f"{where}: unknown error {expect['error']}")
        elif set(expect) != {"value"}:
            problems.append(f"{where}: expects exactly value or error")
    return len(data["cases"])


def unb64url(text, length):
    """Decode base64url without padding to exactly `length` bytes, or None."""
    if not isinstance(text, str) or not B64URL.match(text):
        return None
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError):
        return None
    if len(raw) != length or base64.urlsafe_b64encode(raw).rstrip(b"=").decode() != text:
        return None
    return raw


def verify_signature(case):
    """What a reader returns for this case: "valid" or an outcome code."""
    sig = case["signature_file"]
    if set(sig) != {"alg", "publisher", "key", "signature"} or not all(
        isinstance(v, str) for v in sig.values()
    ):
        return "bad_signature_file"
    signature = unb64url(sig["signature"], 64)
    if signature is None:
        return "bad_signature_file"
    if sig["alg"] != "ed25519":
        return "unknown_alg"
    public = unb64url(case["public_key"], 32)
    try:
        text = case["message_b64"]
        message = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        Ed25519PublicKey.from_public_bytes(public).verify(
            signature, SIGNATURE_CONTEXTS[case["context"]] + message
        )
    except (InvalidSignature, TypeError, ValueError, binascii.Error):
        return "bad_signature"
    return "valid"


def check_signatures(path, problems, codes):
    data = json.loads(path.read_text())
    names = set()
    for i, case in enumerate(data["cases"]):
        where = f"{path.name} case {i} ({case.get('name')})"
        name = case.get("name")
        if not name or name in names:
            problems.append(f"{where}: missing or duplicate name")
        names.add(name)
        if case.get("context") not in SIGNATURE_CONTEXTS:
            problems.append(f"{where}: context must be manifest, feed or keys")
            continue
        if not isinstance(case.get("signature_file"), dict) or not all(
            isinstance(case.get(k), str) for k in ("public_key", "message_b64")
        ):
            problems.append(f"{where}: needs public_key, message_b64 and signature_file")
            continue
        expect = case.get("expect")
        if expect != "valid" and expect not in codes:
            problems.append(f"{where}: unknown expectation {expect!r}")
            continue
        got = verify_signature(case)
        if got != expect:
            problems.append(f"{where}: expected {expect}, the re-check gives {got}")
    return len(data["cases"])


def verify_endorsement(keys_bytes, sig_bytes, endorser):
    """True when keys.sig is a keys-context signature over keys_bytes by `endorser`.

    `endorser` is the (publisher, id, public_key) the reader holds for the key
    the signature names, or None when the reader holds none.
    """
    try:
        sig = json.loads(sig_bytes)
    except ValueError:
        return False
    if not isinstance(sig, dict) or set(sig) != {"alg", "publisher", "key", "signature"}:
        return False
    if not all(isinstance(v, str) for v in sig.values()) or sig["alg"] != "ed25519":
        return False
    signature = unb64url(sig["signature"], 64)
    public = unb64url(endorser[2], 32) if endorser else None
    if signature is None or public is None:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(
            signature, SIGNATURE_CONTEXTS["keys"] + keys_bytes
        )
    except InvalidSignature:
        return False
    return True


def instant(text):
    """A timestamp as a point in time, so +01:00 and Z compare as instants. Raises ValueError."""
    if not isinstance(text, str):
        raise ValueError("not a string")
    value = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    if value.tzinfo is None:
        raise ValueError("no offset")
    return value


def parse_key_set(data):
    """A key set's keys by id, or None when it doesn't parse or repeats an id."""
    try:
        keys = data["keys"]
        ids = [k["id"] for k in keys]
        if not isinstance(data["publisher"], str) or not keys or len(set(ids)) != len(ids):
            return None
        instant(data["updated_at"])
        for k in keys:
            for end in ("retired_at", "revoked_at"):
                if end in k:
                    instant(k[end])
    except (KeyError, TypeError, ValueError):
        return None
    return {k["id"]: k for k in keys}


def key_set_outcome(case, keys_bytes, sig_bytes):
    """What a reader returns for this key set: accepted, needs_approval,
    bad_endorsement or key_set_rollback."""
    # Refused before anything else, and before any map by id is built.
    try:
        new = json.loads(keys_bytes)
    except ValueError:
        return "bad_key_set"
    new_keys = parse_key_set(new)
    previous = case["previous"]
    if new_keys is None or (previous is not None and parse_key_set(previous) is None):
        return "bad_key_set"
    publisher = new["publisher"]
    if previous is not None:
        if previous["publisher"] != publisher:
            return "bad_endorsement"
        # Rollback is refused before any endorsement is looked at.
        if instant(new["updated_at"]) < instant(previous["updated_at"]):
            return "key_set_rollback"
        for old in previous["keys"]:
            now = new_keys.get(old["id"])
            if now is None or any(old.get(end) and not now.get(end) for end in ("retired_at", "revoked_at")):
                return "key_set_rollback"
            if old.get("revoked_at") and not now.get("revoked_at"):
                return "key_set_rollback"
        # A compromised key can't come back under a fresh id.
        revoked = {k["public_key"]: k["id"] for k in previous["keys"] if k.get("revoked_at")}
        if any(revoked.get(k["public_key"], k["id"]) != k["id"] for k in new["keys"]):
            return "key_set_rollback"
        held = {k["id"]: k for k in previous["keys"]}
    else:
        held = {p["id"]: {"public_key": p["public_key"]} for p in case["pins"]
                if p["publisher"] == publisher}
    added = [k for k in new["keys"] if held.get(k["id"], {}).get("public_key") != k["public_key"]]
    if sig_bytes is None:
        return "needs_approval" if added else "accepted"
    try:
        sig = json.loads(sig_bytes)
        name = (sig["publisher"], sig["key"])
    except (ValueError, KeyError, TypeError):
        return "bad_endorsement"
    if name[0] != publisher:
        return "bad_endorsement"
    endorser = held.get(name[1])
    revoked_now = bool(new_keys.get(name[1], {}).get("revoked_at"))
    if previous is not None:
        # The key must be in the previous set, neither retired nor revoked there, and
        # the new set mustn't revoke it: a compromised key can't vouch for its own revocation.
        if endorser is None or endorser.get("retired_at") or endorser.get("revoked_at") or revoked_now:
            return "bad_endorsement"
    elif endorser is None or revoked_now:
        # Stateless: only a pinned key the new set doesn't revoke counts. Any other
        # signature is no endorsement at all, not a bad one.
        return "needs_approval" if added else "accepted"
    if not verify_endorsement(keys_bytes, sig_bytes, (name[0], name[1], endorser["public_key"])):
        return "bad_endorsement"
    return "accepted"


def check_key_sets(directory, problems, codes):
    if not directory.is_dir():
        problems.append(f"{directory.name}: missing")
        return 0
    cases = sorted(p for p in directory.iterdir() if p.is_dir())
    names = set()
    for case_dir in cases:
        where = f"key-sets/{case_dir.name}"
        try:
            case = json.loads((case_dir / "case.json").read_text())
            keys_bytes = (case_dir / "keys.json").read_bytes()
            json.loads(keys_bytes)
        except (OSError, ValueError) as err:
            problems.append(f"{where}: needs case.json and keys.json that parse: {err}")
            continue
        if case.get("name") != case_dir.name or case["name"] in names:
            problems.append(f"{where}: name must be the directory's and unique")
        names.add(case.get("name"))
        if set(case) != {"name", "previous", "pins", "expect"}:
            problems.append(f"{where}: case.json holds name, previous, pins and expect")
            continue
        if case["expect"] != "accepted" and case["expect"] not in codes:
            problems.append(f"{where}: unknown expectation {case['expect']!r}")
            continue
        sig_path = case_dir / "keys.sig"
        sig_bytes = sig_path.read_bytes() if sig_path.exists() else None
        got = key_set_outcome(case, keys_bytes, sig_bytes)
        if got != case["expect"]:
            problems.append(f"{where}: expected {case['expect']}, the re-check gives {got}")
    return len(cases)


def read_zip(data):
    """A bundle zip's entries as {path: bytes}, or None if it isn't a readable zip."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    except (zipfile.BadZipFile, OSError):
        return None


def signature_outcome(sig_bytes, context, message, trust, expected_publisher, pinned):
    """What a reader makes of a signature file over `message`: {"status": "verified",
    "publisher", "key"}, {"status": "unverified"} when there is none, or {"error": code}.

    `trust` is {"pins", "key_sets"}; `pinned` says whether `expected_publisher` has a
    pinned key, which makes an unsigned file an error.
    """
    if sig_bytes is None:
        return {"error": "unsigned_from_pinned_publisher"} if pinned else {"status": "unverified"}
    try:
        sig = json.loads(sig_bytes)
    except ValueError:
        return {"error": "bad_signature_file"}
    if not isinstance(sig, dict) or set(sig) != {"alg", "publisher", "key", "signature"} or not all(
        isinstance(v, str) for v in sig.values()
    ):
        return {"error": "bad_signature_file"}
    signature = unb64url(sig["signature"], 64)
    if signature is None:
        return {"error": "bad_signature_file"}
    if sig["alg"] != "ed25519":
        return {"error": "unknown_alg"}
    # The keys the reader trusts: pins, and the keys of each key set for its publisher.
    trusted = [p for p in trust["pins"]]
    for ks in trust["key_sets"]:
        trusted += [dict(k, publisher=ks["publisher"]) for k in ks["keys"]]
    found = [k for k in trusted if k["publisher"] == sig["publisher"] and k["id"] == sig["key"]]
    if not found:
        return {"error": "unknown_key"}
    key = found[0]
    if any(k.get("revoked_at") for k in found):
        return {"error": "revoked_key"}
    try:
        Ed25519PublicKey.from_public_bytes(unb64url(key["public_key"], 32)).verify(
            signature, SIGNATURE_CONTEXTS[context] + message
        )
    except (InvalidSignature, TypeError, ValueError):
        return {"error": "bad_signature"}
    if expected_publisher is not None and sig["publisher"] != expected_publisher:
        return {"error": "publisher_mismatch"}
    return {"status": "verified", "publisher": sig["publisher"], "key": sig["key"]}


def bundle_outcome(case, entries, pinned=None):
    """What a reader returns for this bundle: {"status", ...} or {"error": code}.

    `pinned` defaults to whether a pin names the expected publisher.
    """
    if pinned is None:
        pinned = any(p["publisher"] == case["expected_publisher"] for p in case["trust"]["pins"])
    # manifest.sig first: a bad signature is refused before the bundle's own checks.
    status = signature_outcome(entries.get("manifest.sig"), "manifest", entries.get("manifest.json", b""),
                               case["trust"], case["expected_publisher"], pinned)
    if "error" in status:
        return status
    # The bundle's own checks.
    try:
        listed = {f["path"]: f["sha256"] for f in json.loads(entries["manifest.json"])["files"]}
    except (KeyError, ValueError, TypeError):
        return {"error": "bad_bundle"}
    present = {path for path in entries if path not in ("manifest.json", "manifest.sig")}
    if present != set(listed):
        return {"error": "bad_bundle"}
    for path, digest in listed.items():
        if hashlib.sha256(entries[path]).hexdigest() != digest:
            return {"error": "bad_bundle"}
    return status


def check_bundles(directory, problems, codes):
    if not directory.is_dir():
        problems.append(f"{directory.name}: missing")
        return 0
    cases = sorted(p for p in directory.iterdir() if p.is_dir())
    for case_dir in cases:
        where = f"bundles/{case_dir.name}"
        try:
            case = json.loads((case_dir / "case.json").read_text())
            entries = read_zip((case_dir / "bundle.zip").read_bytes())
        except (OSError, ValueError) as err:
            problems.append(f"{where}: needs case.json that parses and bundle.zip: {err}")
            continue
        if entries is None or "manifest.json" not in entries:
            problems.append(f"{where}: bundle.zip isn't a zip with a manifest.json")
            continue
        if set(case) != {"name", "trust", "expected_publisher", "expect"} or set(case["trust"]) != {
            "pins", "key_sets"
        }:
            problems.append(f"{where}: case.json holds name, trust (pins, key_sets), expected_publisher and expect")
            continue
        if case["name"] != case_dir.name:
            problems.append(f"{where}: name must be the directory's")
        expect = case["expect"]
        if set(expect) == {"error"}:
            if expect["error"] not in codes:
                problems.append(f"{where}: {expect['error']} isn't in spec/feeds.md § Outcomes")
        elif expect.get("status") not in ("verified", "unverified"):
            problems.append(f"{where}: expects status verified or unverified, or an error")
            continue
        got = bundle_outcome(case, entries)
        if got != expect:
            problems.append(f"{where}: expected {expect}, the re-check gives {got}")
    return len(cases)


class VectorProblem(Exception):
    """The vector itself is broken, as opposed to a feed a reader refuses."""


def feed_index_problem(index_bytes, validator):
    """True when a plain feed index is bad_feed: not JSON, not a valid feed, a repeated
    stream id, or a bundle path that isn't bundles/<its sha256>.zip."""
    try:
        feed = json.loads(index_bytes)
    except ValueError:
        return True
    if any(True for _ in validator.iter_errors(feed)):
        return True
    ids = [s["id"] for s in feed["streams"]]
    if len(set(ids)) != len(ids):
        return True
    return any(s["bundle"] != f"bundles/{s['sha256']}.zip" for s in feed["streams"])


def feed_outcome(case, files, validator):
    """What a reader returns for this feed: {"index": "ok" or a code, "streams": {id: outcome}}.

    `files` are the feed's files by path, and `validator` checks a feed index against
    its schema. The order is § Reading a feed's.
    """
    connection, state = case["connection"], case["state"]

    def refused(code):
        return {"index": code, "streams": {}}

    if "feed.json" in files and "feed.json.age" in files:
        return refused("plain_and_encrypted")
    publisher = connection["feed"].split("/", 1)[0]
    # Stateless: only the connection's pins. With state: those, approved keys and held key sets.
    trust = {
        "pins": list(connection.get("keys", [])) + (list(state["approved"]) if state else []),
        "key_sets": list(state["key_sets"].values()) if state else [],
    }
    pinned = any(p["publisher"] == publisher for p in trust["pins"]) or any(
        ks["publisher"] == publisher for ks in trust["key_sets"])
    index_bytes = files.get("feed.json", b"")
    got = signature_outcome(files.get("feed.sig"), "feed", index_bytes, trust, publisher, pinned)
    if "error" in got:
        return refused(got["error"])
    if feed_index_problem(index_bytes, validator):
        return refused("bad_feed")
    feed = json.loads(index_bytes)
    if feed["id"] != connection["feed"] or feed["publisher"] != publisher:
        return refused("wrong_feed")
    if state is not None and instant(feed["updated_at"]) < instant(state["feed_updated_at"]):
        return refused("stale_feed")
    held = state["streams"] if state is not None else {}
    listed = {s["id"]: s for s in feed["streams"]}
    streams = {sid: "withdrawn" for sid in held if sid not in listed}
    for sid, stream in listed.items():
        streams[sid] = stream_outcome(stream, held.get(sid), files, feed["id"], trust, publisher, pinned)
    return {"index": "ok", "streams": streams}


def stream_outcome(stream, held, files, feed_id, trust, publisher, pinned):
    """One stream of a feed: accepted, unchanged or an outcome code."""
    if held is not None and held["sha256"] == stream["sha256"]:
        return "unchanged"
    data = files.get(stream["bundle"])
    if data is None:
        raise VectorProblem(f"stream {stream['id']}: {stream['bundle']} is missing from the vector")
    if hashlib.sha256(data).hexdigest() != stream["sha256"]:
        return "download_mismatch"
    entries = read_zip(data)
    if entries is None or "manifest.json" not in entries:
        return "bad_bundle"
    got = bundle_outcome({"trust": trust, "expected_publisher": publisher}, entries, pinned)
    if "error" in got:
        return got["error"]
    if got["status"] == "verified":
        manifest = json.loads(entries["manifest.json"])
        if "published_at" not in manifest:
            return "missing_published_at"
        place = manifest.get("feed") or {}
        if place.get("id") != feed_id:
            return "wrong_feed"
        if place.get("stream") != stream["id"]:
            return "wrong_stream"
        if held is not None and instant(manifest["published_at"]) <= instant(held["published_at"]):
            return "replay"
    return "accepted"


def check_feeds(directory, problems, codes):
    if not directory.is_dir():
        problems.append(f"{directory.name}: missing")
        return 0
    registry = load_registry()
    validators = {
        name: Draft202012Validator(
            json.loads((ROOT / "schemas" / name / "v1.json").read_text()),
            registry=registry, format_checker=FormatChecker())
        for name in ("org.legiblerecords.feed", "org.legiblerecords.feed-connection")
    }
    cases = sorted(p for p in directory.iterdir() if p.is_dir())
    for case_dir in cases:
        where = f"feeds/{case_dir.name}"
        try:
            case = json.loads((case_dir / "case.json").read_text())
            files = {p.relative_to(case_dir / "feed").as_posix(): p.read_bytes()
                     for p in (case_dir / "feed").rglob("*") if p.is_file()}
        except (OSError, ValueError) as err:
            problems.append(f"{where}: needs case.json that parses and a feed/ directory: {err}")
            continue
        if set(case) != {"name", "connection", "state", "expect"} or set(case["expect"]) != {"index", "streams"}:
            problems.append(f"{where}: case.json holds name, connection, state and expect (index, streams)")
            continue
        if case["name"] != case_dir.name:
            problems.append(f"{where}: name must be the directory's")
        for err in validators["org.legiblerecords.feed-connection"].iter_errors(case["connection"]):
            problems.append(f"{where}: the connection isn't a valid feed-connection: {err.message}")
        expect = case["expect"]
        outcomes = [expect["index"]] + list(expect["streams"].values())
        unknown = [o for o in outcomes if o not in codes | {"ok", "accepted", "unchanged", "withdrawn"}]
        if unknown:
            problems.append(f"{where}: {unknown} aren't in spec/feeds.md § Outcomes")
            continue
        try:
            got = feed_outcome(case, files, validators["org.legiblerecords.feed"])
        except VectorProblem as err:
            problems.append(f"{where}: {err}")
            continue
        if got != expect:
            problems.append(f"{where}: expected {expect}, the re-check gives {got}")
    return len(cases)


def main():
    problems = []
    count = 0
    codes = outcome_codes()
    if codes is None:
        problems.append("spec/feeds.md has no table under '## Outcomes'")
        codes = set()
    for path in sorted(ROOT.glob("vectors/schema-language*.json")):
        count += check_schema_language(path, problems)
    count += check_restricted_yaml(ROOT / "vectors" / "restricted-yaml.json", problems)
    count += check_signatures(ROOT / "vectors" / "signatures.json", problems, codes)
    count += check_key_sets(ROOT / "vectors" / "key-sets", problems, codes)
    count += check_bundles(ROOT / "vectors" / "bundles", problems, codes)
    count += check_feeds(ROOT / "vectors" / "feeds", problems, codes)
    for p in problems:
        print(f"FAIL {p}")
    print(f"{count} vector cases checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
