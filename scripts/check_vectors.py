#!/usr/bin/env python3
"""Check that the test vectors are well formed.

This doesn't run an implementation: it checks the vectors themselves, so a
mistake in them is caught before an implementation is tested against it.

- every case has a unique name and the keys its kind needs;
- every expected body is a valid JSON Schema 2020-12 schema;
- every restricted-YAML case expects either a value or a known error.

- every key-set case, re-checked under rules written here, gives its expected outcome;
- every signature case verifies, or fails with its expected code, under a
  re-check written here rather than imported from make_vectors.py.

Needs: pip install jsonschema cryptography
"""

import base64
import binascii
import json
import re
import sys
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
SIGNATURE_CODES = {"bad_signature_file", "unknown_alg", "bad_signature"}
KEY_SET_OUTCOMES = {"accepted", "needs_approval", "bad_endorsement"}
B64URL = re.compile(r"^[A-Za-z0-9_-]*$")
OPTIONS = {"base", "common", "location"}


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


def check_signatures(path, problems):
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
        if expect != "valid" and expect not in SIGNATURE_CODES:
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


def key_set_outcome(case, keys_bytes, sig_bytes):
    """What a reader returns for this key set: accepted, needs_approval or bad_endorsement."""
    new = json.loads(keys_bytes)
    previous = case["previous"]
    publisher = new["publisher"]
    held = {}  # (publisher, id) -> key entry the reader already trusts
    if previous is not None:
        held = {(previous["publisher"], k["id"]): k for k in previous["keys"]}
    else:
        held = {(p["publisher"], p["id"]): {"public_key": p["public_key"]} for p in case["pins"]}
    added = [
        k for k in new["keys"]
        if held.get((publisher, k["id"]), {}).get("public_key") != k["public_key"]
    ]
    if sig_bytes is None:
        return "needs_approval" if added else "accepted"
    try:
        sig = json.loads(sig_bytes)
        name = (sig["publisher"], sig["key"])
    except (ValueError, KeyError, TypeError):
        return "bad_endorsement"
    endorser = held.get(name)
    if previous is not None:
        # Against the previous accepted set: the key must be in it, neither retired nor revoked.
        if endorser is None or endorser.get("retired_at") or endorser.get("revoked_at"):
            return "bad_endorsement"
    else:
        # Stateless: only a pinned key counts, and the new set mustn't revoke it. A key
        # that isn't pinned is no endorsement at all, not a bad one.
        if endorser is None:
            return "needs_approval" if added else "accepted"
    if name[0] != publisher:
        return "bad_endorsement"
    # Either way, a key the new set revokes can't vouch for it.
    if any(k["id"] == name[1] and k.get("revoked_at") for k in new["keys"]):
        return "bad_endorsement"
    if not verify_endorsement(keys_bytes, sig_bytes, (name[0], name[1], endorser["public_key"])):
        return "bad_endorsement"
    return "accepted"


def check_key_sets(directory, problems):
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
        if case["expect"] not in KEY_SET_OUTCOMES:
            problems.append(f"{where}: unknown expectation {case['expect']!r}")
            continue
        sig_path = case_dir / "keys.sig"
        sig_bytes = sig_path.read_bytes() if sig_path.exists() else None
        got = key_set_outcome(case, keys_bytes, sig_bytes)
        if got != case["expect"]:
            problems.append(f"{where}: expected {case['expect']}, the re-check gives {got}")
    return len(cases)


def main():
    problems = []
    count = 0
    for path in sorted(ROOT.glob("vectors/schema-language*.json")):
        count += check_schema_language(path, problems)
    count += check_restricted_yaml(ROOT / "vectors" / "restricted-yaml.json", problems)
    count += check_signatures(ROOT / "vectors" / "signatures.json", problems)
    count += check_key_sets(ROOT / "vectors" / "key-sets", problems)
    for p in problems:
        print(f"FAIL {p}")
    print(f"{count} vector cases checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
