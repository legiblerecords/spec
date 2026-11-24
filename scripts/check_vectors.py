#!/usr/bin/env python3
"""Check that the test vectors are well formed.

This doesn't run an implementation: it checks the vectors themselves, so a
mistake in them is caught before an implementation is tested against it.

- every case has a unique name and the keys its kind needs;
- every expected body is a valid JSON Schema 2020-12 schema;
- every restricted-YAML case expects either a value or a known error.

- every key-set case, re-checked under rules written here (the key set validated against
  its schema first, timestamps parsed as strict RFC 3339, the reader's clock from "now"),
  gives its expected outcome;
- every bundle case, opened as a zip and re-checked here (entry names, signature in the
  order of spec/records.md § Reading a signed bundle, trust as in spec/feeds.md § Trust,
  then manifest hashes and file list), gives its expected outcome;
- every feed case, re-checked here step by step in the order of spec/feeds.md § Reading a
  feed (the served key set, revocation, the index, each stream), gives its expected key
  set, index and stream outcomes, and the reader state it expects after the poll; its
  connection and reader state are well formed;
- every outcome code a vector expects is in the table in spec/feeds.md § Outcomes;
- every signature case verifies, or fails with its expected code.

Nothing here is imported from make_vectors.py. LEGIBLE_VECTORS_MUTATION turns a check off,
for scripts/check_mutations.py.

Needs: pip install jsonschema cryptography
"""

import base64
import binascii
import copy
import hashlib
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone
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
# LEGIBLE_VECTORS_MUTATION=<name>[,<name>…] turns a check off, so that scripts/check_mutations.py
# can show the vectors catch its absence: feed-sig-verify, manifest-sig-verify, zip-names,
# future-skew, served-key-set, revocation-clears, forget-unaccepted, revocation-drops-floors.
MUTATIONS = set(filter(None, os.environ.get("LEGIBLE_VECTORS_MUTATION", "").split(",")))
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
    # alg before the signature is decoded: another algorithm's signature has another length.
    if sig["alg"] != "ed25519":
        return "unknown_alg"
    signature = unb64url(sig["signature"], 64)
    if signature is None:
        return "bad_signature_file"
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


DEFAULT_NOW = "2026-12-01T00:00:00Z"  # the reader's clock when a case gives no "now"
SKEW = timedelta(hours=24)  # a timestamp further ahead of the clock than this is refused
RFC3339 = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|([+-])(\d{2}):(\d{2}))$")


def instant(text):
    """An RFC 3339 date-time as a point in time, so +01:00 and Z compare as instants.

    Strict: the full date, a time with seconds, and an offset are required, and every
    field must be in range. Raises ValueError for anything else.
    """
    match = RFC3339.match(text) if isinstance(text, str) else None
    if not match:
        raise ValueError(f"not an RFC 3339 date-time: {text!r}")
    year, month, day, hour, minute, second = (int(g) for g in match.groups()[:6])
    fraction = match.group(7)
    if match.group(8) in ("Z", "z"):
        offset = timedelta(0)
    else:
        hours, minutes = int(match.group(10)), int(match.group(11))
        if hours > 23 or minutes > 59:
            raise ValueError(f"offset out of range: {text!r}")
        offset = timedelta(hours=hours, minutes=minutes) * (1 if match.group(9) == "+" else -1)
    # RFC 3339 allows a leap second; it is the same instant as the end of that minute.
    leap = second == 60
    value = datetime(year, month, day, hour, minute, 59 if leap else second,
                     int((fraction[1:] + "000000")[:6]) if fraction else 0, tzinfo=timezone(offset))
    return value + timedelta(seconds=1) if leap else value


def too_far_ahead(text, now):
    """True when the timestamp is more than SKEW after the reader's clock `now`."""
    return "future-skew" not in MUTATIONS and instant(text) - now > SKEW


def key_bytes(text):
    """A public key's bytes, from canonical base64url, or None."""
    return unb64url(text, 32)


def parse_signature_file(data):
    """A signature file's members, or None unless it is a JSON object with exactly the
    four string members. Doesn't look at alg or decode the signature."""
    try:
        sig = json.loads(data)
    except (ValueError, TypeError):
        return None
    if not isinstance(sig, dict) or set(sig) != {"alg", "publisher", "key", "signature"}:
        return None
    if not all(isinstance(v, str) for v in sig.values()):
        return None
    return sig


def verifies(public, signature, context, message):
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, SIGNATURE_CONTEXTS[context] + message)
    except (InvalidSignature, TypeError, ValueError):
        return False
    return True


class Trust:
    """The keys a reader trusts, as feeds.md § Trust defines them.

    `anchors` are pinned and approved keys ({publisher, id, alg, public_key}); `held` maps a
    publisher to the key set the reader holds for it (one accepted on this poll included);
    `revoking` are served sets that passed key-set step 1 but aren't held (waiting for
    approval, bad_endorsement, key_set_rollback): their revocations refuse signatures on this
    poll, and clear nothing.
    """

    def __init__(self, anchors, held, revoking=()):
        self.anchors = list(anchors)
        self.held = dict(held)
        self.revoking = list(revoking)

    def trusts_publisher(self, publisher):
        return publisher in self.held or any(a["publisher"] == publisher for a in self.anchors)

    def sources(self, publisher, key_id):
        """Every (alg, public key bytes) the reader's sources give for this key id."""
        found = [(a["alg"], key_bytes(a["public_key"])) for a in self.anchors
                 if a["publisher"] == publisher and a["id"] == key_id]
        entry = self.held_entry(publisher, key_id)
        if entry is not None:
            found.append((entry["alg"], key_bytes(entry["public_key"])))
        return found

    def held_entry(self, publisher, key_id):
        held = self.held.get(publisher)
        return next((k for k in held["keys"] if k["id"] == key_id), None) if held else None

    def revoked(self, publisher, key_id, public, held_only=False):
        """True when a held set, or unless `held_only` a revoking one, revokes this id, or this
        public key under any id."""
        sets = [self.held.get(publisher)]
        if not held_only:
            sets += [s for s in self.revoking if s["publisher"] == publisher]
        return any(k.get("revoked_at") and (k["id"] == key_id or key_bytes(k["public_key"]) == public)
                   for s in sets if s for k in s["keys"])

    def alias(self, publisher, key_id, public):
        """True when `key_id` is pinned or approved and the held set, or a served set that
        passed step 1 (held or revoking), lists these public key bytes under another id."""
        if not any(a["publisher"] == publisher and a["id"] == key_id for a in self.anchors):
            return False
        sets = [self.held.get(publisher)] + [s for s in self.revoking if s["publisher"] == publisher]
        return any(k["id"] != key_id and key_bytes(k["public_key"]) == public
                   for s in sets if s for k in s["keys"])

    def lookup(self, publisher, key_id):
        """The key's public bytes, or {"error": code}: records.md § Reading a signed bundle, step 1.5."""
        found = set(self.sources(publisher, key_id))
        if not found:
            return {"error": "unknown_key"}
        if len(found) > 1:
            # The sources disagree about this id: none of them is trusted.
            return {"error": "unknown_key"}
        alg, public = found.pop()
        if self.revoked(publisher, key_id, public):
            return {"error": "revoked_key"}
        if self.alias(publisher, key_id, public) and "pin-alias" not in MUTATIONS:
            # A pinned or approved key whose bytes a key set lists under another id: one key,
            # one name, so the pin doesn't count.
            return {"error": "unknown_key"}
        if alg != "ed25519":
            return {"error": "unknown_alg"}
        return public

    def signer_revoked(self, signer):
        """For a signer the reader recorded: has the held set revoked its key since? Only a held
        revocation clears state (feeds.md § Trust)."""
        held_only = "forget-unaccepted" not in MUTATIONS
        found = self.sources(signer["publisher"], signer["key"]) or [(None, None)]
        return any(self.revoked(signer["publisher"], signer["key"], public, held_only) for _, public in found)


def signature_outcome(sig_bytes, context, message, trust, expected_publisher, trusted):
    """What a reader makes of a signature file over `message`, in the order of records.md
    § Reading a signed bundle: {"status": "verified", "publisher", "key"}, {"status":
    "unverified"} when there is none, or {"error": code}.

    `trusted` says whether the reader trusts the expected publisher (feeds.md § Trust),
    which makes an unsigned file an error.
    """
    if sig_bytes is None:
        return {"error": "unsigned_from_pinned_publisher"} if trusted else {"status": "unverified"}
    sig = parse_signature_file(sig_bytes)  # 1. the signature file
    if sig is None:
        return {"error": "bad_signature_file"}
    if sig["alg"] != "ed25519":  # 2. alg, before the signature is decoded
        return {"error": "unknown_alg"}
    signature = unb64url(sig["signature"], 64)  # 3. a canonical 64-byte signature
    if signature is None:
        return {"error": "bad_signature_file"}
    if expected_publisher is not None and sig["publisher"] != expected_publisher:  # 4.
        return {"error": "publisher_mismatch"}
    public = trust.lookup(sig["publisher"], sig["key"])  # 5. the key
    if isinstance(public, dict):
        return public
    skip = f"{context}-sig-verify" in MUTATIONS
    if not skip and not verifies(public, signature, context, message):  # 6. the signature
        return {"error": "bad_signature"}
    return {"status": "verified", "publisher": sig["publisher"], "key": sig["key"]}


def key_set_problem(data, validator, now, fetched_from):
    """Why a key set as served is bad_key_set (records.md § Key sets, step 1), or None."""
    try:
        new = json.loads(data)
    except (ValueError, TypeError):
        return "not JSON"
    if any(True for _ in validator.iter_errors(new)):
        return "not a valid org.legiblerecords.keys"
    ids = [k["id"] for k in new["keys"]]
    if len(set(ids)) != len(ids):
        return "a key id twice"
    raw = [key_bytes(k["public_key"]) for k in new["keys"]]
    if any(r is None for r in raw):
        return "a public_key that isn't canonical base64url of 32 bytes"
    if len(set(raw)) != len(raw):
        return "one public key under two ids"
    try:
        for k in new["keys"]:
            for field in ("created_at", "retired_at", "revoked_at"):
                if field in k:
                    instant(k[field])
        if too_far_ahead(new["updated_at"], now):
            return "updated_at too far ahead"
    except ValueError:
        return "a timestamp that isn't RFC 3339"
    if fetched_from is not None and new["publisher"] != fetched_from:
        return "publisher isn't the domain it was fetched from"
    return None


def decide_key_set(keys_bytes, sig_bytes, previous, anchors, now, validator, fetched_from=None):
    """What a reader decides about a served key set (records.md § Key sets): (outcome, set),
    the set being the parsed key set when it is valid, else None.

    `previous` is the set the reader holds, or None; `anchors` its pinned and approved keys.
    """
    if key_set_problem(keys_bytes, validator, now, fetched_from) is not None:  # 1. Parse
        return "bad_key_set", None
    new = json.loads(keys_bytes)
    publisher = new["publisher"]
    new_by_id = {k["id"]: k for k in new["keys"]}
    if previous is not None:  # 2. Rollback
        if previous["publisher"] != publisher:
            return "bad_endorsement", new
        if instant(new["updated_at"]) < instant(previous["updated_at"]):
            return "key_set_rollback", new
        for old in previous["keys"]:
            now_ = new_by_id.get(old["id"])
            if now_ is None or any(old.get(end) and not now_.get(end) for end in ("retired_at", "revoked_at")):
                return "key_set_rollback", new
        revoked_bytes = {key_bytes(k["public_key"]): k["id"] for k in previous["keys"] if k.get("revoked_at")}
        if any(revoked_bytes.get(key_bytes(k["public_key"]), k["id"]) != k["id"] for k in new["keys"]):
            return "key_set_rollback", new
    trust = Trust([a for a in anchors if a["publisher"] == publisher],
                  {publisher: previous} if previous is not None else {})
    added = [k for k in new["keys"]
             if (k["alg"], key_bytes(k["public_key"])) not in set(trust.sources(publisher, k["id"]))]
    endorsed = False
    if sig_bytes is not None:  # 3. Endorsement: every failure is bad_endorsement
        sig = parse_signature_file(sig_bytes)
        if sig is None or sig["alg"] != "ed25519" or unb64url(sig["signature"], 64) is None:
            return "bad_endorsement", new
        if sig["publisher"] != publisher:
            return "bad_endorsement", new
        found = set(trust.sources(publisher, sig["key"]))
        if len(found) == 1:  # otherwise no anchor, or anchors that disagree: no endorsement
            alg, public = found.pop()
            held = trust.held_entry(publisher, sig["key"])
            if held is not None and (held.get("retired_at") or held.get("revoked_at")):
                return "bad_endorsement", new
            if trust.revoked(publisher, sig["key"], public):
                return "bad_endorsement", new
            if new_by_id.get(sig["key"], {}).get("revoked_at") or any(
                    k.get("revoked_at") and key_bytes(k["public_key"]) == public for k in new["keys"]):
                return "bad_endorsement", new
            if alg != "ed25519" or not verifies(public, unb64url(sig["signature"], 64), "keys", keys_bytes):
                return "bad_endorsement", new
            endorsed = True
    if endorsed:  # 4.
        return "accepted", new
    return ("needs_approval" if added else "accepted"), new  # 5.


def keys_validator():
    return Draft202012Validator(
        json.loads((ROOT / "schemas" / "org.legiblerecords.keys" / "v1.json").read_text()),
        registry=load_registry(), format_checker=FormatChecker())


def check_key_sets(directory, problems, codes):
    if not directory.is_dir():
        problems.append(f"{directory.name}: missing")
        return 0
    validator = keys_validator()
    cases = sorted(p for p in directory.iterdir() if p.is_dir())
    names = set()
    for case_dir in cases:
        where = f"key-sets/{case_dir.name}"
        try:
            case = json.loads((case_dir / "case.json").read_text())
            keys_bytes = (case_dir / "keys.json").read_bytes()
        except (OSError, ValueError) as err:
            problems.append(f"{where}: needs a case.json that parses, and keys.json: {err}")
            continue
        if case.get("name") != case_dir.name or case["name"] in names:
            problems.append(f"{where}: name must be the directory's and unique")
        names.add(case.get("name"))
        if not {"name", "previous", "pins", "expect"} <= set(case) <= {"name", "previous", "pins", "expect", "now"}:
            problems.append(f"{where}: case.json holds name, previous, pins, expect and optionally now")
            continue
        if case["previous"] is not None and any(True for _ in validator.iter_errors(case["previous"])):
            problems.append(f"{where}: previous isn't a valid org.legiblerecords.keys")
            continue
        if any(set(p) != {"publisher", "id", "alg", "public_key"} for p in case["pins"]):
            problems.append(f"{where}: every pin has publisher, id, alg and public_key")
            continue
        if case["expect"] != "accepted" and case["expect"] not in codes:
            problems.append(f"{where}: unknown expectation {case['expect']!r}")
            continue
        sig_path = case_dir / "keys.sig"
        sig_bytes = sig_path.read_bytes() if sig_path.exists() else None
        try:
            now = instant(case.get("now", DEFAULT_NOW))
        except ValueError as err:
            problems.append(f"{where}: {err}")
            continue
        got, _ = decide_key_set(keys_bytes, sig_bytes, case["previous"], case["pins"], now, validator)
        if got != case["expect"]:
            problems.append(f"{where}: expected {case['expect']}, the re-check gives {got}")
    return len(cases)


BAD_NAMES = "bad zip entry names"


def read_zip(data):
    """A bundle zip's entries as {path: bytes}; BAD_NAMES when two entries share a name or a
    name is absolute, has a backslash, or has a . or .. segment (records.md § Bundles); None
    if it isn't a readable zip."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if "zip-names" not in MUTATIONS and (len(set(names)) != len(names) or any(
                    n.startswith("/") or "\\" in n or any(seg in (".", "..") for seg in n.split("/"))
                    for n in names)):
                return BAD_NAMES
            return {i.filename: z.read(i) for i in infos if not i.is_dir()}
    except (zipfile.BadZipFile, OSError):
        return None


def bundle_outcome(entries, trust, expected_publisher, trusted, now):
    """What a reader returns for an opened bundle: {"status", ...} or {"error": code}.

    The signature is checked first, then the bundle's own checks (records.md § Reading a
    signed bundle).
    """
    status = signature_outcome(entries.get("manifest.sig"), "manifest", entries.get("manifest.json", b""),
                               trust, expected_publisher, trusted)
    if "error" in status:
        return status
    try:
        manifest = json.loads(entries["manifest.json"])
        listed = {f["path"]: f["sha256"] for f in manifest["files"]}
        if "published_at" in manifest and too_far_ahead(manifest["published_at"], now):
            return {"error": "bad_bundle"}
    except (KeyError, ValueError, TypeError):
        return {"error": "bad_bundle"}
    present = {path for path in entries if path not in ("manifest.json", "manifest.sig")}
    if present != set(listed):
        return {"error": "bad_bundle"}
    for path, digest in listed.items():
        if hashlib.sha256(entries[path]).hexdigest() != digest:
            return {"error": "bad_bundle"}
    return status


def open_bundle(data):
    """A bundle's entries, or {"error": "bad_bundle"} when its zip can't be read as one."""
    entries = read_zip(data)
    if entries is None or entries == BAD_NAMES or "manifest.json" not in entries:
        return {"error": "bad_bundle"}
    return entries


def check_bundles(directory, problems, codes):
    if not directory.is_dir():
        problems.append(f"{directory.name}: missing")
        return 0
    cases = sorted(p for p in directory.iterdir() if p.is_dir())
    for case_dir in cases:
        where = f"bundles/{case_dir.name}"
        try:
            case = json.loads((case_dir / "case.json").read_text())
            data = (case_dir / "bundle.zip").read_bytes()
        except (OSError, ValueError) as err:
            problems.append(f"{where}: needs case.json that parses and bundle.zip: {err}")
            continue
        if read_zip(data) is None:
            problems.append(f"{where}: bundle.zip isn't a zip")
            continue
        keys = {"name", "trust", "expected_publisher", "expect"}
        if not keys <= set(case) <= keys | {"now"} or set(case["trust"]) != {"pins", "key_sets"}:
            problems.append(f"{where}: case.json holds name, trust (pins, key_sets), expected_publisher, "
                            "expect and optionally now")
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
        trust = Trust(case["trust"]["pins"], {ks["publisher"]: ks for ks in case["trust"]["key_sets"]})
        entries = open_bundle(data)
        if "error" in entries:
            got = entries
        else:
            got = bundle_outcome(entries, trust, case["expected_publisher"],
                                 trust.trusts_publisher(case["expected_publisher"]),
                                 instant(case.get("now", DEFAULT_NOW)))
        if got != expect:
            problems.append(f"{where}: expected {expect}, the re-check gives {got}")
    return len(cases)


class VectorProblem(Exception):
    """The vector itself is broken, as opposed to a feed a reader refuses."""


def feed_index_problem(index_bytes, validator, now):
    """True when a plain feed index is bad_feed (feeds.md § Reading a feed, step 5): not JSON,
    not a valid feed, a repeated stream id, a bundle path that isn't bundles/<its
    sha256>.zip, or an updated_at too far ahead of the reader's clock."""
    try:
        feed = json.loads(index_bytes)
    except ValueError:
        return True
    if any(True for _ in validator.iter_errors(feed)):
        return True
    ids = [s["id"] for s in feed["streams"]]
    if len(set(ids)) != len(ids):
        return True
    if any(s["bundle"] != f"bundles/{s['sha256']}.zip" for s in feed["streams"]):
        return True
    try:
        for s in feed["streams"]:
            instant(s["published_at"])
        return too_far_ahead(feed["updated_at"], now)
    except ValueError:
        return True


def feed_outcome(case, files, served, validators):
    """What a reader returns for this feed: ({"index": "ok" or a code, "streams": {id: outcome}},
    and "key_set" when the publisher serves one; the reader state after the poll, or None).

    `files` are the feed's files by path, `served` the key-set/ files. The steps are
    numbered as in spec/feeds.md § Reading a feed.
    """
    connection = case["connection"]
    state = copy.deepcopy(case["state"])
    now = instant(case.get("now", DEFAULT_NOW))
    publisher = connection["feed"].split("/", 1)[0]
    anchors = list(connection.get("keys", [])) + (list(state["approved"]) if state else [])
    held = dict(state["key_sets"]) if state else {}
    result = {"index": None, "streams": {}}

    # 1. The publisher's key set, decided with the held set and the anchors.
    revoking, served_valid = [], False
    if "keys.json" in served:
        outcome, new = decide_key_set(served["keys.json"], served.get("keys.sig"), held.get(publisher),
                                      anchors, now, validators["keys"], fetched_from=publisher)
        result["key_set"] = outcome
        try:
            served_valid = not any(True for _ in validators["keys"].iter_errors(json.loads(served["keys.json"])))
        except ValueError:
            served_valid = False
        if "served-key-set" not in MUTATIONS:
            if outcome == "accepted":
                held[publisher] = new
            elif new is not None:
                # Passed step 1 but isn't held: its revocations count on this poll only.
                revoking.append(new)
    trust = Trust(anchors, held, revoking)
    trusted = trust.trusts_publisher(publisher) or served_valid
    if state is not None:
        state["key_sets"] = held

    # 2. Clear what a key revoked by the held set signed: drop the stream's sha256 and signer,
    # keep its published_at as the replay floor; drop the index's signer, keep its updated_at.
    if state is not None and "revocation-clears" not in MUTATIONS:
        drop_floors = "revocation-drops-floors" in MUTATIONS
        for sid, held_stream in list(state["streams"].items()):
            if held_stream["signer"] is not None and trust.signer_revoked(held_stream["signer"]):
                if drop_floors:
                    del state["streams"][sid]
                else:
                    state["streams"][sid] = dict(held_stream, sha256=None, signer=None)
                result["streams"][sid] = "revoked_key"
        if state["feed_signer"] is not None and trust.signer_revoked(state["feed_signer"]):
            state["feed_signer"] = None
            if drop_floors:
                state["feed_updated_at"] = None

    def refused(code):
        result["index"] = code
        return result, state

    # 3. Fetch the index.
    if "feed.json" in files and "feed.json.age" in files:
        return refused("plain_and_encrypted")
    index_bytes = files.get("feed.json", b"")
    # 4. feed.sig.
    got = signature_outcome(files.get("feed.sig"), "feed", index_bytes, trust, publisher, trusted)
    if "error" in got:
        return refused(got["error"])
    # 5. A valid index.
    if feed_index_problem(index_bytes, validators["feed"], now):
        return refused("bad_feed")
    feed = json.loads(index_bytes)
    # 6. The right feed.
    if feed["id"] != connection["feed"] or feed["publisher"] != publisher:
        return refused("wrong_feed")
    # 7. Not stale.
    if state is not None and state["feed_updated_at"] is not None and \
            instant(feed["updated_at"]) < instant(state["feed_updated_at"]):
        return refused("stale_feed")
    result["index"] = "ok"
    if state is not None:
        state["feed_updated_at"] = feed["updated_at"]
        state["feed_signer"] = ({"publisher": got["publisher"], "key": got["key"]}
                                if got["status"] == "verified" else None)

    held_streams = dict(state["streams"]) if state is not None else {}
    listed = {s["id"]: s for s in feed["streams"]}
    for sid in held_streams:  # 9. Withdrawn: in the state, not in the index.
        if sid not in listed and sid not in result["streams"]:
            result["streams"][sid] = "withdrawn"
            del state["streams"][sid]
    for sid, stream in listed.items():
        if sid in result["streams"]:  # revoked_key in step 2: not checked again on this poll
            continue
        outcome, signer = stream_outcome(stream, held_streams.get(sid), files, feed["id"], trust,
                                         publisher, trusted, now)
        result["streams"][sid] = outcome
        if outcome == "accepted" and state is not None:  # 13. Recorded.
            state["streams"][sid] = {"sha256": stream["sha256"], "published_at": stream["published_at"],
                                     "signer": signer}
    return result, state


def stream_outcome(stream, held, files, feed_id, trust, publisher, trusted, now):
    """One stream of a feed, steps 8 and 10 to 13: (accepted, signer), or (unchanged or an
    outcome code, None). A stream a revocation cleared has no sha256, so it is never unchanged."""
    outcome = stream_check(stream, held, files, feed_id, trust, publisher, trusted, now)
    if isinstance(outcome, dict):
        return "accepted", outcome.get("signer")
    return outcome, None


def stream_check(stream, held, files, feed_id, trust, publisher, trusted, now):
    """stream_outcome's checks: {"signer": ...} when accepted, else the outcome."""
    if held is not None and held["sha256"] == stream["sha256"]:  # 8.
        return "unchanged"
    data = files.get(stream["bundle"])  # 10.
    if data is None:
        raise VectorProblem(f"stream {stream['id']}: {stream['bundle']} is missing from the vector")
    if hashlib.sha256(data).hexdigest() != stream["sha256"]:
        return "download_mismatch"
    entries = open_bundle(data)
    if "error" in entries:
        return entries["error"]
    got = bundle_outcome(entries, trust, publisher, trusted, now)
    if "error" in got:
        return got["error"]
    manifest = json.loads(entries["manifest.json"])
    if "published_at" not in manifest:  # 11. Signed or not.
        return "missing_published_at"
    if instant(manifest["published_at"]) != instant(stream["published_at"]):
        return "bad_bundle"
    if got["status"] == "verified":
        place = manifest.get("feed") or {}
        if place.get("id") != feed_id:
            return "wrong_feed"
        if place.get("stream") != stream["id"]:
            return "wrong_stream"
        # 12. Replay, against the floor a revocation keeps too.
        if held is not None and instant(manifest["published_at"]) <= instant(held["published_at"]):
            return "replay"
        return {"signer": {"publisher": got["publisher"], "key": got["key"]}}  # 13.
    return {"signer": None}


def state_problem(state):
    """Why a feed case's reader state isn't in the vectors' format, or None."""
    if state is None:
        return None
    if set(state) != {"feed_updated_at", "feed_signer", "streams", "key_sets", "approved"}:
        return "state holds feed_updated_at, feed_signer, streams, key_sets and approved"
    signers = [state["feed_signer"]] + [s.get("signer", "missing") for s in state["streams"].values()]
    if any(s is not None and (not isinstance(s, dict) or set(s) != {"publisher", "key"}) for s in signers):
        return "feed_signer and every stream's signer are {publisher, key} or null"
    if any(set(s) != {"sha256", "published_at", "signer"} for s in state["streams"].values()):
        return "every stream holds sha256, published_at and signer"
    if any(s["sha256"] is None and s["signer"] is not None for s in state["streams"].values()):
        return "a stream a revocation cleared has sha256 and signer null"
    if any(set(a) != {"publisher", "id", "alg", "public_key"} for a in state["approved"]):
        return "every approved key has publisher, id, alg and public_key"
    return None


def check_feeds(directory, problems, codes):
    if not directory.is_dir():
        problems.append(f"{directory.name}: missing")
        return 0
    registry = load_registry()
    validators = {
        short: Draft202012Validator(
            json.loads((ROOT / "schemas" / name / "v1.json").read_text()),
            registry=registry, format_checker=FormatChecker())
        for short, name in (("feed", "org.legiblerecords.feed"),
                            ("connection", "org.legiblerecords.feed-connection"),
                            ("keys", "org.legiblerecords.keys"))
    }
    cases = sorted(p for p in directory.iterdir() if p.is_dir())
    for case_dir in cases:
        where = f"feeds/{case_dir.name}"
        try:
            case = json.loads((case_dir / "case.json").read_text())
            files = {p.relative_to(case_dir / "feed").as_posix(): p.read_bytes()
                     for p in (case_dir / "feed").rglob("*") if p.is_file()}
            served = {p.name: p.read_bytes() for p in (case_dir / "key-set").glob("*") if p.is_file()}
        except (OSError, ValueError) as err:
            problems.append(f"{where}: needs case.json that parses and a feed/ directory: {err}")
            continue
        keys = {"name", "connection", "state", "expect"}
        if not keys <= set(case) <= keys | {"now"}:
            problems.append(f"{where}: case.json holds name, connection, state, expect and optionally now")
            continue
        expect = case["expect"]
        if set(expect) - {"state"} != {"index", "streams"} | ({"key_set"} if served else set()):
            problems.append(f"{where}: expect holds index and streams, key_set exactly when there is key-set/, "
                            "and optionally state")
            continue
        if "state" in expect and (case["state"] is None or state_problem(expect["state"])):
            problems.append(f"{where}: expect's state is for a case with state, in the state's format")
            continue
        if served and set(served) - {"keys.json", "keys.sig"} or served and "keys.json" not in served:
            problems.append(f"{where}: key-set/ holds keys.json and optionally keys.sig")
            continue
        if case["name"] != case_dir.name:
            problems.append(f"{where}: name must be the directory's")
        problem = state_problem(case["state"])
        if problem:
            problems.append(f"{where}: {problem}")
            continue
        for err in validators["connection"].iter_errors(case["connection"]):
            problems.append(f"{where}: the connection isn't a valid feed-connection: {err.message}")
        outcomes = [expect["index"], expect.get("key_set", "ok")] + list(expect["streams"].values())
        unknown = [o for o in outcomes if o not in codes | {"ok", "accepted", "unchanged", "withdrawn"}]
        if unknown:
            problems.append(f"{where}: {unknown} aren't in spec/feeds.md § Outcomes")
            continue
        try:
            got, after = feed_outcome(case, files, served, validators)
        except VectorProblem as err:
            problems.append(f"{where}: {err}")
            continue
        if "state" in expect:
            got["state"] = after
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
