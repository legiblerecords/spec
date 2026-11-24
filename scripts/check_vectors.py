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
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

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


def bundle_outcome(case, entries):
    """What a reader returns for this bundle: {"status", ...} or {"error": code}."""
    # manifest.sig first: a bad signature is refused before the bundle's own checks.
    status = {"status": "unverified"}
    publisher_pinned = any(p["publisher"] == case["expected_publisher"] for p in case["trust"]["pins"])
    sig_bytes = entries.get("manifest.sig")
    if sig_bytes is None:
        if publisher_pinned:
            return {"error": "unsigned_from_pinned_publisher"}
    else:
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
        trusted = [p for p in case["trust"]["pins"]]
        for ks in case["trust"]["key_sets"]:
            trusted += [dict(k, publisher=ks["publisher"]) for k in ks["keys"]]
        found = [k for k in trusted if k["publisher"] == sig["publisher"] and k["id"] == sig["key"]]
        if not found:
            return {"error": "unknown_key"}
        key = found[0]
        if any(k.get("revoked_at") for k in found):
            return {"error": "revoked_key"}
        try:
            Ed25519PublicKey.from_public_bytes(unb64url(key["public_key"], 32)).verify(
                signature, SIGNATURE_CONTEXTS["manifest"] + entries.get("manifest.json", b"")
            )
        except (InvalidSignature, TypeError, ValueError):
            return {"error": "bad_signature"}
        if case["expected_publisher"] is not None and sig["publisher"] != case["expected_publisher"]:
            return {"error": "publisher_mismatch"}
        status = {"status": "verified", "publisher": sig["publisher"], "key": sig["key"]}
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
    for p in problems:
        print(f"FAIL {p}")
    print(f"{count} vector cases checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
