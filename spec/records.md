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

## Bundles

Several records, with or without attachments, travel as a bundle: a directory, or a zip of one.

```
manifest.json
manifest.sig          (optional)
records/<kind>/<key>.json
files/<sha256>
```

`manifest.json` is itself a record, of type [`org.legiblerecords.bundle`](../schemas/org.legiblerecords.bundle/v1.yaml). It lists every file with its path, SHA-256, and for records their `$type` and `version`. `manifest.sig` is the only file in a bundle that the manifest doesn't list; any other unlisted file is an error.

A reader of a bundle checks that:

- every file's hash matches the manifest;
- every file the manifest lists is present, and every file present is listed, except `manifest.sig`;
- every reference resolves to a record or attachment in the bundle.

Any failure is an error, not a warning: in a security record, a broken link is usually the thing that matters.

### Publication fields

The manifest has two more optional fields, so that a signature can say more than "this publisher made these bytes": it says the publisher offered this bundle as the current version of a stream, at a time. Adding them doesn't change the type's version.

| Field | Holds |
|---|---|
| `published_at` | `common.datetime`: when the publisher made this bundle. A bundle in a feed must have it. |
| `feed` | `{ id, stream }`: the feed and stream the bundle was published for, when it was published in one. `id` is `<publisher>/<slug>`, and `stream` is a `common.slug`. |

A **publisher** is a domain the signer controls, written as a lowercase domain: labels of letters, digits and hyphens, none starting or ending with a hyphen, at least two labels joined by `.`, at most 253 characters, with no scheme, port or path. It is [`common.domain`](../schemas/org.legiblerecords.common/v1.yaml); everything in this spec that names a publisher, including the `<publisher>` in a feed id, uses that pattern.

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

- `alg` is `ed25519`. A reader refuses any other value (`unknown_alg`): a new algorithm is a new `alg`.
- `publisher` is the domain that holds the key, and `key` is the key's id there. A publisher that serves no key set still names a domain it controls, such as a client's own, so that two publishers can't collide.
- `signature` is 64 bytes, and a public key is 32 bytes, both in base64url without padding.
- The four members are required and no others are allowed. A file that isn't this JSON is `bad_signature_file`.

The signature covers a **context string** followed by the exact bytes of `manifest.json` as stored in the bundle:

```
legible-records/v1 manifest\n
```

then the bytes. The context string ends in a newline. Every kind of signature in Legible Records has its own context (`manifest`, `feed`, `keys`), so a key that signs more than one kind of thing can't have one passed off as another. The reader checks the bytes it has, not a re-serialization of them. The manifest lists every file's SHA-256, so the signature covers every record and attachment.

Ed25519 is deterministic, so a signer given the same key and manifest writes the same `manifest.sig`. [vectors/signatures.json](../vectors/signatures.json) fixes keys, messages and expected outcomes: each case gives a context, a public key, the message bytes (`message_b64`), a `signature_file`, and `valid` or the outcome code a reader returns. The private keys behind the vectors are published in `scripts/make_vectors.py` for testing only; never sign anything real with them.

### Reading a signed bundle

In addition to the checks above:

1. If `manifest.sig` is present, find the key named by `publisher` and `key` among the keys the reader trusts, and verify the signature over the context string and `manifest.json`'s bytes. A signature that doesn't verify, names an unknown algorithm, names an unknown key, or was made by a revoked key is an error, not a downgrade to unverified.
2. If it is absent, the bundle is **unverified**. A reader says so wherever it shows the bundle, and may refuse it by policy. A reader that has pinned a key for the bundle's publisher refuses an unsigned bundle from it.

### Encrypted bundles

To travel over email or another transport you don't trust, a bundle's zip is encrypted with [age](https://age-encryption.org/v1), binary or armored, conventionally named `.zip.age`. Nothing inside changes.

- A reader recognizes one by its first bytes (`age-encryption.org/v1` or `-----BEGIN AGE ENCRYPTED FILE-----`), not its name, and after decrypting checks it like any other bundle.
- Encryption hides the contents, not the file's name, its rough size, or that it was sent.
- Encryption shows the bundle wasn't changed in transit, not who made it: anyone with the recipient's key or the passphrase can make one. A signed bundle's signature is inside the zip, so it is checked after decrypting: encryption hides the contents, and the signature says who made them.
- A passphrase goes by a different channel than the bundle, and never on a command line.

## Sensitivity labels

A schema can say what kind of data a field holds, with a label from a data taxonomy (`@user.contact.email` in the short form, `x-data` in JSON Schema). Labels tell a reader, a publisher or an agent how to handle a field before reading its value. Legible Records doesn't require a particular taxonomy; types say which they use.
