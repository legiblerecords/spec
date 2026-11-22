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
records/<kind>/<key>.json
files/<sha256>
```

`manifest.json` is itself a record, of type [`org.legiblerecords.bundle`](../schemas/org.legiblerecords.bundle/v1.yaml). It lists every file with its path, SHA-256, and for records their `$type` and `version`.

A reader of a bundle checks that:

- every file's hash matches the manifest;
- every file the manifest lists is present, and every file present is listed;
- every reference resolves to a record or attachment in the bundle.

Any failure is an error, not a warning: in a security record, a broken link is usually the thing that matters.

### Encrypted bundles

To travel over email or another transport you don't trust, a bundle's zip is encrypted with [age](https://age-encryption.org/v1), binary or armored, conventionally named `.zip.age`. Nothing inside changes.

- A reader recognizes one by its first bytes (`age-encryption.org/v1` or `-----BEGIN AGE ENCRYPTED FILE-----`), not its name, and after decrypting checks it like any other bundle.
- Encryption hides the contents, not the file's name, its rough size, or that it was sent.
- Encryption shows the bundle wasn't changed in transit, not who made it: anyone with the recipient's key or the passphrase can make one. Signing bundles is not yet part of this spec.
- A passphrase goes by a different channel than the bundle, and never on a command line.

## Sensitivity labels

A schema can say what kind of data a field holds, with a label from a data taxonomy (`@user.contact.email` in the short form, `x-data` in JSON Schema). Labels tell a reader, a publisher or an agent how to handle a field before reading its value. Legible Records doesn't require a particular taxonomy; types say which they use.
