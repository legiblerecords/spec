# Records and bundles

Status: draft.

## A record

A record is one JSON object, in a UTF-8 file with the extension `.json`.

| Field | Required | Meaning |
|---|---|---|
| `$type` | yes | The type's identifier, a reverse domain name such as `tech.monorail.controls.control`. |
| `version` | yes | The type's major version, an integer. |
| `produced_by` | no | What wrote the file: `app`, and optionally `build` and `output`. Defined in [`org.legiblerecords.common`](../schemas/org.legiblerecords.common/v1.yaml). |
| `source` | no | What it was built from: `system` (such as `track`), `refs` (identifiers in that system, such as commit ids) and `as_of`. |
| `body` | depends on the type | The record's main content: Markdown unless the type says otherwise. |

Every other field is the type's own.

### Reading a record

- Check `$type` and `version` before anything else. A reader that doesn't know the type, or only knows an older major version, says so rather than guessing.
- Accept fields you don't know, and keep them when you rewrite the record.
- Show a value from an open list that you don't know as written.

### Writing a record

- Write only the fields the type defines.
- Write keys in sorted order, numbers in their shortest form, and end the file with one newline, so the same content always gives the same bytes.

## Type identifiers

A type identifier is a domain its author controls, reversed, followed by the type's name: `tech.monorail.controls.control` for a type published by monorail.tech. Segments are lowercase letters, digits and hyphens.

- Types are grouped by what they describe, not by the app that writes them, so a type keeps its name when another app starts writing it.
- A published type's identifier never changes. A breaking change is a new major version; a change in meaning is a new type.
- The type's schema is at the `$id` its author publishes, conventionally `https://<domain>/schemas/<type>/v<major>.json`.

## References

A reference from one record to another is a string `kind:key`, such as `control:mfa-company-accounts`, where `kind` is the referenced type's short name (its `title`) and `key` is that record's `id`. A reference may name a part of the record after `#`, as in `policy:access-control#scope`. Its form is `common.refString`. A reference resolves within the set of records it travels with: a bundle, or a directory a tool is reading.

A reference to an attachment is an object:

```json
{ "sha256": "…", "name": "access-review-q3.pdf", "media_type": "application/pdf" }
```

### Pointing at records elsewhere

A `kind:key` reference must resolve in the records it travels with. Three shapes in `org.legiblerecords.common` point at things that don't: an external reference, an identifier and a person match. A reader never resolves any of them inside a bundle, so none can make a bundle `bad_bundle`.

**An external reference** (`common.externalRef`) names a record that travels elsewhere, in another stream or from another publisher:

```json
{ "type": "tech.monorail.policy.document", "key": "access-control",
  "publisher": "acme.example", "revision": 3, "sha256": "…" }
```

- `type` is the record's `$type`, the full type identifier (not the short name a `kind:key` reference uses), and `key` its `id`. `publisher` is absent when the record is the referring record's publisher's own.
- `revision` is for types that number their own revisions, such as a policy. It is not the type's `version`.
- `sha256` is the SHA-256 of the record's content line ([§ Content lines](#content-lines)), pinning exactly what it said.
- A reader that holds the target resolves the reference, and shows one it can't resolve as unresolved. When the hash doesn't match the record it holds under that key and revision, it holds different content, and says so.

**An identifier** (`common.identifier`) is something's id in one system, `{ "system": "github", "id": "acme/api" }`. The two halves together are the key: they match when both are exactly equal. `system` is lowercase free text, such as `github`, `gitlab`, `okta`, `entra`, `google`, `slack` or `serial`; a misspelt system matches nothing, and a reader shows that, rather than matching something else.

A system name means one kind of id, so that two publishers describing the same thing write the same identifier. For a system that has a stable id and a changeable name, the system's own name means the stable id, and the name gets a system of its own:

| System | `id` is | Example |
|---|---|---|
| `github` | for a person or account, the numeric user id; for a repository, `owner/name` | `4183920`, `acme/api` |
| `github-login` | a GitHub login | `ana-lima-acme` |
| `gitlab` | as `github` | `1290331`, `acme/tools` |
| `okta`, `entra`, `google` | the directory's user id, not the sign-in name | `00u1ab2cd3` |
| `serial` | a device's serial number, as printed | `C02XK1ABCD` |

**A person match** (`common.personMatch`) is what a publisher knows about the person a record is about, when it doesn't know the reader's key for them:

```json
{ "emails": ["ana@acme.example"], "identifiers": [{ "system": "okta", "id": "00u1ab2cd3" }], "name": "Ana Lima" }
```

- It has `emails` or `identifiers`, or both. A match with neither can't be matched; a reader shows it as unresolved.
- A reader matches identifiers first, against the identifiers of the people it holds. Only when no identifier matches anyone does it compare emails, case-insensitively.
- A match to no one, or to more than one person, is left unresolved and shown to a person. A reader never chooses between candidates.
- `name` is for the people resolving a match. It is never matched on.

### Content lines

A record's **content line** is its canonical line ([§ Record sets](#record-sets)) with the top-level fields `produced_by` and `source` removed, and without the final `\n`. Its SHA-256, in lowercase hex, is the record's **content hash**.

- Provenance doesn't change content: republishing a record from a new build, or a later export, keeps its hash. A change to anything else the record says changes it.
- Only top-level `produced_by` and `source` are removed; a field of that name inside another object is content.
- The hash is over the canonical form, not over the bytes of a per-record file, which writers may format as they like.

[vectors/content-lines.json](../vectors/content-lines.json) gives records, their content lines and their hashes; `plain` and `provenance-removed` hash alike, and `changed-field` differs.

## Bundles

Several records, with or without attachments, travel as a bundle: a directory, or a zip of one.

```
manifest.json
manifest.sig          (optional)
records/<kind>/<key>.json
records/<kind>.ndjson   (a record set; see § Record sets)
files/<sha256>
```

`manifest.json` is itself a record, of type [`org.legiblerecords.bundle`](../schemas/org.legiblerecords.bundle/v1.yaml). It lists every file with its path, SHA-256, and for records their `$type` and `version` (and, for a record set, its `count`). `manifest.sig` is the only file in a bundle that the manifest doesn't list; any other unlisted file is an error.

A reader of a bundle checks that:

- every file's hash matches the manifest;
- every file the manifest lists is present, and every file present is listed, except `manifest.sig`;
- each `kind:key` appears exactly once in the bundle, whether in a per-record file or a record set, and whatever the record's version;
- every record set meets [§ Record sets](#record-sets);
- every reference resolves to a record or attachment in the bundle;
- `published_at`, when the manifest has it, is no more than 24 hours after the reader's clock.

Any failure is an error, not a warning: in a security record, a broken link is usually the thing that matters. A reader returns `bad_bundle` for any of them ([feeds.md § Outcomes](feeds.md#outcomes)).

In a zip, every entry name is a path relative to the bundle's root, with `/` separators. Before it reads any entry, a reader refuses (`bad_bundle`) a zip with two entries of the same name, a name that starts with `/`, a name with a `\`, or a name with a `.` or `..` segment. Two entries named `manifest.json` could otherwise show two readers two different manifests, and the others could write outside the directory a bundle is unpacked into.

### Record sets

A bundle can hold many records of one type in one file, a **record set**, so that a large dataset (vulnerability status for every repository, every device, every acknowledgment in a company) needs one zip entry rather than one per record, and a reader can process it as a stream.

**The rule.** Each `kind:key` appears exactly once in a bundle, whether in a per-record file or a record set, and whatever the record's version. References name no version, so this is what makes every reference resolve to one record. A repeated `kind:key` is `bad_bundle`.

**Layout.** A record set is the file `records/<kind>.ndjson`, where `<kind>` is named as for a per-record file's folder ([§ References](#references)): the type's short name (its schema's `title`). A reader that doesn't have the type's schema takes the file name as the kind, as it does a per-record folder, provided it is a key. There is at most one per kind, because its name is its kind. A set holds records of one `$type` and one `version`; a bundle that mixes versions of a type puts one version in the set and the other in per-record files, and the rule above keeps their keys apart. A bundle may use both forms for different kinds, or for one kind across versions.

**Lines.** One complete Legible Record per line, with the `$type` and `version` its manifest entry gives and an `id` that is its key.

- The file is UTF-8 with no byte order mark.
- Each line is compact canonical JSON, the same bytes from every writer:
  - no whitespace outside strings;
  - object keys sorted by their UTF-8 bytes (not by UTF-16 code units, as RFC 8785 sorts them), and no key twice;
  - strings as UTF-8, escaping only what JSON requires: `\"`, `\\`, `\b`, `\f`, `\n`, `\r` and `\t`, and every other character from U+0000 to U+001F as `\u00xx` with lowercase hex. Nothing else is escaped, and a lone surrogate is refused;
  - every number read as an IEEE 754 double and written as ECMAScript writes it ([RFC 8785 § 3.2.2.3](https://www.rfc-editor.org/rfc/rfc8785#section-3.2.2.3)): `7.5`, `0.00001`, `1e-7`, `1e+21`, `123456789`. A number whose text isn't that, such as `7.50`, `1e-05`, or an integer too large for a double to hold exactly, isn't canonical. `NaN` and `Infinity` aren't JSON.
- Each line ends with `\n` (not `\r\n`), the last one included. There are no blank lines.
- Lines are sorted by `id`, compared as bytes, and no `id` repeats. The same records therefore always give the same bytes, so a set's hash, and a signature over its manifest, change only when its records do.

**Per-record files.** A per-record file's name is its record's key: when the record has an `id`, it is the file's name without `.json`, and a file whose `id` differs is `bad_bundle`. So each record has one name, whichever form it travels in.

**Manifest.** A record set's entry has `path`, `sha256`, `record_type`, `record_version` and `count`, the number of lines. `count` is required on a record set's entry and not allowed on any other entry.

**Reading.** A reader may read a record set as a stream, hashing as it goes and holding one record at a time. What it has read is provisional until the end of the file, where the SHA-256 and `count` must match the manifest; only then may it commit or pass on the records. A set is `bad_bundle` when:

- a line doesn't parse, or isn't in the canonical form above (including a `\r\n` ending or a byte order mark);
- a line's `$type` or `version` isn't its entry's;
- a line has no `id`, or one that isn't a key;
- an `id` repeats, or lines are out of order;
- there is a blank line, or the file doesn't end with `\n`;
- the `count` or the SHA-256 doesn't match;
- its path isn't `records/<kind>.ndjson`, or its entry has no `count`.

A reader's error names the file and the line. A reader may cap the length of a line, and refuse a longer one as `bad_bundle`; the reference tools cap it at 16 MiB.

**Writing.** A writer puts a kind in a record set when it chooses to. References inside a set's records are checked like any others, and a reference to a key in a set resolves to that line's record.

### Publication fields

The manifest has two more optional fields, so that a signature can say more than "this publisher made these bytes": it says the publisher offered this bundle as the current version of a stream, at a time. Adding them doesn't change the type's version.

| Field | Holds |
|---|---|
| `published_at` | `common.datetime`: when the publisher made this bundle. A bundle in a feed must have it, signed or not (`missing_published_at`), and it must be the instant the feed index gives for the bundle (`bad_bundle`); that value is what a reader records and passes to its destination ([feeds.md § Reading a feed](feeds.md#reading-a-feed)). |
| `feed` | `{ id, stream }`: the feed and stream the bundle was published for, when it was published in one. `id` is `<publisher>/<slug>`, and `stream` is a `common.slug`. |

A **publisher** is a domain the signer controls, written as a lowercase domain: labels of letters, digits and hyphens, none starting or ending with a hyphen, at least two labels joined by `.`, the last of them not all digits (so an IP address is not a publisher), at most 253 characters, with no scheme, port or path. It is [`common.domain`](../schemas/org.legiblerecords.common/v1.yaml); everything in this spec that names a publisher, including the `<publisher>` in a feed id ([`common.feedId`](../schemas/org.legiblerecords.common/v1.yaml)), uses that pattern. The schemas' patterns use no lookahead, so that every regular-expression engine reads them alike, and bound lengths with `maxLength`.

### Signed bundles

`manifest.sig` is a JSON object:

```json
{
  "alg": "ed25519",
  "publisher": "acme.example",
  "key": "2026-11",
  "signature": "<base64url, no padding>"
}
```

- The four members are required, each a string, and no others are allowed. A file that isn't this JSON is `bad_signature_file`.
- `alg` is `ed25519`. A reader refuses any other value (`unknown_alg`): a new algorithm is a new `alg`. It checks `alg` before it decodes `signature`, since another algorithm's signature can have another length.
- `publisher` is the domain that holds the key, and `key` is the key's id there. A publisher that serves no key set still names a domain it controls, such as a client's own, so that two publishers can't collide.
- `signature` is 64 bytes, and a public key is 32 bytes, both in **canonical** base64url: no padding, and the unused low bits of the last character are zero, so every value has exactly one spelling. A `signature` that isn't canonical base64url of 64 bytes is `bad_signature_file`. Keys are compared by their decoded bytes, never by their text.

The signature covers a **context string** followed by the exact bytes of `manifest.json` as stored in the bundle:

```
legible-records/v1 manifest\n
```

then the bytes. The context string ends in a newline. Every kind of signature in Legible Records has its own context (`manifest`, `feed`, `keys`), so a key that signs more than one kind of thing can't have one passed off as another. The reader checks the bytes it has, not a re-serialization of them. The manifest lists every file's SHA-256, so the signature covers every record and attachment.

Ed25519 is deterministic, so a signer given the same key and manifest writes the same `manifest.sig`. [vectors/signatures.json](../vectors/signatures.json) fixes keys, messages and expected outcomes: each case gives a context, a public key, the message bytes (`message_b64`), a `signature_file`, and `valid` or the outcome code a reader returns. The private keys behind the vectors are published in `scripts/make_vectors.py` for testing only; never sign anything real with them.

### Key sets

A publisher that controls a domain can serve its keys there, as a record of type [`org.legiblerecords.keys`](../schemas/org.legiblerecords.keys/v1.yaml) at

```
https://<publisher>/.well-known/legible-records/keys.json
```

```json
{
  "$type": "org.legiblerecords.keys",
  "version": 1,
  "publisher": "acme.example",
  "updated_at": "2026-11-24T00:00:00Z",
  "keys": [
    { "id": "2026-11", "alg": "ed25519", "public_key": "<base64url>", "created_at": "2026-11-24T00:00:00Z" },
    { "id": "2025-06", "alg": "ed25519", "public_key": "<base64url>", "created_at": "2025-06-01T00:00:00Z", "retired_at": "2026-11-24T00:00:00Z" },
    { "id": "2024-01", "alg": "ed25519", "public_key": "<base64url>", "created_at": "2024-01-01T00:00:00Z", "revoked_at": "2025-06-01T00:00:00Z" }
  ]
}
```

It is served over HTTPS, and that is what ties a key to a name: whoever controls the domain controls its key set. `publisher` is the domain it is served from; a set fetched from one domain that names another is `bad_key_set`. `keys` has at least one key; a key's `id` is unique in the set, and so is its public key: one key listed under two ids is `bad_key_set`. Every `public_key` is canonical base64url ([§ Signed bundles](#signed-bundles)); a set with one that isn't is `bad_key_set`. A reader never verifies with a key whose `alg` it doesn't know, and a signature that names one is `unknown_alg`.

**Retired and revoked.** A key's life ends in one of two ways.

- `retired_at` is ordinary rotation: the publisher stopped signing with the key. Bundles it signed still verify, whatever their `published_at`, because the key was never compromised.
- `revoked_at` means the key is compromised. Nothing it signed verifies, at any `published_at`, because whoever holds the key can write any date into a manifest. A signature by a revoked key is `revoked_key`. A reader that comes to hold a key set that revokes a key re-checks what it already holds, and treats every bundle that key signed as no longer verified: a feed reader fetches and checks again every stream the key signed, keeping the stream's `published_at` and the index's `updated_at` as replay floors ([feeds.md § Trust](feeds.md#trust)). The publisher re-signs and republishes what should stay, with a `published_at` later than the one readers hold, since they keep it as a replay floor. A revocation that applies only from a date was considered and dropped for the same reason. A key that has both is revoked, and a reader never clears either date from a key it has seen.

**Endorsement.** A reader keeps the last key set it accepted. A key set may be served with `keys.sig`, at `/.well-known/legible-records/keys.sig`: the signature file of [§ Signed bundles](#signed-bundles) with the context `keys`, made over the exact bytes of `keys.json` as served. A key set carries `updated_at`, when the publisher last changed it. A reader's **anchors** for a publisher are the keys of the set it holds for it, its pinned keys and the keys a person approved ([feeds.md § Trust](feeds.md#trust)). A key is **new** when no anchor has the same id, `alg` and public key: a key whose public key or `alg` changed under a held id is new. A reader decides about a key set this way:

1. **Parse.** A key set is refused as `bad_key_set` before any other check, and the reader keeps the set it holds, when it isn't JSON, isn't a valid record of its type, lists the same key `id` twice, lists the same public key under two ids, has a `public_key` that isn't canonical base64url, has an `updated_at` more than 24 hours after the reader's clock, or names a `publisher` other than the domain it was fetched from. A reader never picks one of two entries for an id: whichever it picked, a publisher or a server could make it the wrong one. A far-future `updated_at` would make every later genuine set look like a rollback.
2. **Rollback.** A reader that holds a previous key set refuses the new one as `key_set_rollback`, signed or not, and keeps the one it holds, when the new set's `updated_at` is earlier than the held set's, when it leaves out a key the held set lists, or when it removes a held key's `retired_at` or `revoked_at` (a revoked key never becomes anything else), or when it lists, under any other id, the public key of a key the held set revokes (a compromised key can't come back under a fresh id). This runs before everything below, so a genuine old key set replayed by whoever serves the domain, or an unsigned one that quietly re-activates a key, changes nothing the reader holds (its revocations still count on that poll, as below). The new set's `publisher` must also be the held set's, or the key set is refused as `bad_endorsement` (a reader that fetched the set has already refused it as `bad_key_set` in step 1). An equal `updated_at` is not a rollback. Timestamps are parsed and compared as instants, not as text, so `+01:00` and `Z` compare by when they are.
3. **Endorsement.** With `keys.sig`, every failure below is `bad_endorsement`; the codes `bad_signature_file` and `unknown_alg` are for `manifest.sig` and `feed.sig` only. In this order:
   - `keys.sig` must be the signature file of [§ Signed bundles](#signed-bundles): JSON, the four string members, `alg` `ed25519`, and a canonical 64-byte `signature`.
   - It must name this key set's `publisher`.
   - The key it names must be one of the reader's anchors for that publisher, with no two of them disagreeing about that id ([feeds.md § Trust](feeds.md#trust)). A key that is no anchor is **no endorsement**, not a bad one, and neither is an anchor whose public key the held set or the new set lists under another id (one key, one name): the reader goes on as in step 5, as if the set were unsigned.
   - The anchor may not be retired or revoked in the held set, and the new set may not revoke it. The new set may retire it, which is how a rotation retires the key that signs it, but a compromised key can't vouch for a set that says so.
   - The signature must verify, with the `keys` context, over the exact bytes of `keys.json` (one made with another context, such as `manifest`, doesn't).
4. With a valid endorsement the reader accepts the key set, new keys included, without asking.
5. Without a valid endorsement (no `keys.sig`, or one by a key that is no anchor or is an alias), a key set with a new key is `needs_approval`: a person decides, or the reader's policy is to trust the domain's key set as served (trust on HTTPS). A key set with no new key is accepted, so ending a key's life never needs an endorsement. A set waiting for approval is not held.

That last rule has a cost the spec accepts: whoever controls the server can mark keys retired or revoked without a signature, and a reader will honor it, holding the set if it adds no key and honouring its revocations on that poll if it does ([feeds.md § Trust](feeds.md#trust)). That can deny service, because bundles signed by a key marked revoked stop verifying until the publisher fixes the key set and the reader accepts a newer one. It can't make a bad bundle verify. A reader can't tell this from a real revocation, and a real revocation has to be believed quickly.

**Revocations in a set that isn't held.** A served set that passes step 1 has its revocations honoured on the poll it is served, whatever steps 2 to 5 make of it: waiting for approval, `bad_endorsement` or `key_set_rollback`. They only refuse, on that poll, what the revoked key signed (`revoked_key`); they change nothing the reader keeps. Only a revocation in the set the reader holds, one it accepts on this poll included, clears what a key signed ([feeds.md § Trust](feeds.md#trust)). Anyone who controls the server can serve a set that isn't held, with no key at all, so it may reduce trust for a poll but never move a reader's state.

A reader with no previous key set can still be given **pins**: keys it holds from its configuration, each a publisher, a key id, an `alg` and a public key. A stateless reader keeps nothing between runs, so its pins are its only anchors, and it **cannot detect a rollback**: it has no `updated_at` or end dates to compare, so an old key set it is shown looks current, and a pinned key that the publisher has since retired can still endorse. It accepts a key set when `keys.sig` is by a pinned key that the new set doesn't revoke; the new set may retire it, as in a rotation. If the signature names a pinned key that the new set revokes, or doesn't verify, the key set is `bad_endorsement`, and its revocations are still honoured on that poll, as for any set that passes step 1. A signature by a key that isn't pinned is no endorsement: the key set is `needs_approval` if it has a new key, so a second rotation waits for a person to update the pins, and accepted if it has none.

The outcome codes `bad_key_set`, `bad_endorsement`, `needs_approval` and `key_set_rollback` are defined here, and listed with the rest in [feeds.md § Outcomes](feeds.md#outcomes).

Readers fetch the key set whenever the publisher serves one, on every poll and including readers with pinned keys, so that rotation and revocation reach them ([feeds.md § Trust](feeds.md#trust)). Pinned keys are where that chain starts, not a replacement for it: once a key set is held, it says which of the publisher's keys are retired or revoked, pinned or not.

A **publisher without a key set**, such as a script in a client's CI, still names a domain it controls in `manifest.sig` but serves nothing there. Its public key goes in the reader's configuration and is pinned there; it has no rotation or revocation except a person changing the pin.

[vectors/key-sets/](../vectors/key-sets/) holds the cases, one directory each: `case.json` gives `name`, `previous` (the last accepted key set, or `null`), `pins` (each with `publisher`, `id`, `alg` and `public_key`, as in a connection file), `expect` (`accepted`, `needs_approval`, `bad_endorsement`, `key_set_rollback` or `bad_key_set`), and optionally `now`, the reader's clock (`2026-12-01T00:00:00Z` when absent, for every kind of vector); `keys.json` is the key set as served, which need not be JSON, and `keys.sig` the endorsement when there is one. The key set is taken to be fetched from the domain it names. They use the test keys from `scripts/make_vectors.py`.

### Reading a signed bundle

A reader first reads the zip's entry names, as in [§ Bundles](#bundles). Then it checks the signature, and only then the bundle's own checks, so a bundle with both a bad signature and a changed file is `bad_signature`.

1. If `manifest.sig` is present, the reader checks, in this order, stopping at the first failure:
   1. the signature file: JSON with the four string members (`bad_signature_file`);
   2. `alg` (`unknown_alg`);
   3. `signature`, canonical base64url of 64 bytes (`bad_signature_file`);
   4. that `publisher` is the publisher the reader expects, when it expects one: a feed's, or one given by the caller (`publisher_mismatch`);
   5. the key named by `publisher` and `key`, among the keys the reader trusts ([feeds.md § Trust](feeds.md#trust)): none is `unknown_key`, a revoked one `revoked_key`, and one whose `alg` the reader doesn't know `unknown_alg`;
   6. the signature, over the context string and `manifest.json`'s bytes (`bad_signature`).

   Any failure is an error, not a downgrade to unverified.
2. If it is absent, the bundle is **unverified**. A reader says so wherever it shows the bundle, and may refuse it by policy. A reader that trusts the publisher it expects (a feed's, or one given by the caller), as [feeds.md § Trust](feeds.md#trust) defines, refuses an unsigned bundle from it (`unsigned_from_pinned_publisher`).

[vectors/bundles/](../vectors/bundles/) holds the cases, one directory each: `bundle.zip`, and `case.json` with `name`, `trust` (`pins`, each with `publisher`, `id`, `alg` and `public_key`, and `key_sets`, the key sets the reader holds), `expected_publisher` (the feed's publisher, or `null`), `expect` (`{ status, publisher, key }` for a verified or unverified bundle, or `{ error }` with an outcome code) and optionally `now`. A signature by a key that its key set has revoked is refused even when the revocation is dated after `published_at`.

### Encrypted bundles

To travel over email or another transport you don't trust, a bundle's zip is encrypted with [age](https://age-encryption.org/v1), binary or armored, conventionally named `.zip.age`. Nothing inside changes.

- A reader recognizes one by its first bytes (`age-encryption.org/v1` or `-----BEGIN AGE ENCRYPTED FILE-----`), not its name, and after decrypting checks it like any other bundle.
- Encryption hides the contents, not the file's name, its rough size, or that it was sent.
- Encryption shows the bundle wasn't changed in transit, not who made it: anyone with the recipient's key or the passphrase can make one. A signed bundle's signature is inside the zip, so it is checked after decrypting: encryption hides the contents, and the signature says who made them.
- A passphrase goes by a different channel than the bundle, and never on a command line.

## Sensitivity labels

A schema can say what kind of data a field holds, with a label from a data taxonomy (`@user.contact.email` in the short form, `x-data` in JSON Schema). Labels tell a reader, a publisher or an agent how to handle a field before reading its value. Legible Records doesn't require a particular taxonomy; types say which they use.
