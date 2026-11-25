---
title: Bundles
lede: Several records, with or without attachments, travel together as a bundle. A bundle is a directory, or a zip of one.
---

```text
manifest.json
manifest.sig          (optional)
records/<kind>/<key>.json
records/<kind>.ndjson   (a record set: many records of one kind)
files/<sha256>
```

`manifest.json` is itself a record, of type `org.legiblerecords.bundle`. It lists every file with its path and SHA-256, for records their `$type` and `version`, and for a record set its `count`. `manifest.sig` is the only file the manifest doesn't list.

## What a reader checks

- Every file's hash matches the manifest.
- Every file the manifest lists is present, and every file present is listed, except `manifest.sig`.
- Each `kind:key` appears exactly once, whether in its own file or in a record set, and whatever the record's version.
- Every record set is in canonical form, and its line count matches the manifest.
- Every reference resolves to a record or attachment in the bundle.
- `published_at`, when present, is no more than 24 hours after the reader's clock.

Any failure is an error, not a warning: in a security record, a broken link is usually the thing that matters. The reader returns `bad_bundle`.

Before reading any entry, a reader refuses a zip with two entries of the same name, or a name that starts with `/`, contains `\`, or has a `.` or `..` segment.

## Record sets

A bundle can hold many records of one type in one file, `records/<kind>.ndjson`, so a large dataset, such as vulnerability status for every repository or every policy acknowledgment in a company, needs one zip entry rather than one per record. A reader can process it as a stream, one record at a time.

```text
{"$type":"tech.monorail.policy.acknowledgment","id":"ack-0001","version":1,…}
{"$type":"tech.monorail.policy.acknowledgment","id":"ack-0002","version":1,…}
```

- One complete record per line, all of one `$type` and `version`, each with an `id` that is its key.
- Each line is compact canonical JSON: no whitespace outside strings, keys sorted by their UTF-8 bytes, only the escapes JSON requires, and numbers written as ECMAScript writes them ([RFC 8785](https://www.rfc-editor.org/rfc/rfc8785#section-3.2.2.3)).
- UTF-8 with no byte order mark. Every line ends with `\n`, the last one included, and there are no blank lines.
- Lines are sorted by `id`, compared as bytes, and no `id` repeats.

So the same records always give the same bytes, and a set's hash and signature change only when its records do. The manifest entry for a set gives `count`, the number of lines.

A reader that streams a set treats what it has read as provisional until the end of the file, where the hash and `count` must match the manifest. Only then may it commit the records or pass them on. Any problem is `bad_bundle`, and the error names the file and line.

There is at most one set per kind. A per-record file's name is its record's `id`, so each record has one name whichever form it travels in. A bundle may use both forms, for different kinds, or for one kind across versions.

## Packing and verifying

```sh
legible bundle pack evidence/ -s control.yaml -o evidence.zip
legible bundle verify evidence.zip -s control.yaml
legible bundle unpack evidence.zip -d evidence
```

`pack` treats a `.json` file with `$type` and `version` as a record. Anything else is an attachment, stored by its SHA-256. The reference to put in a record is printed to stderr. The same files always pack to the same bytes.

A kind with more than 1,000 records, across its versions, is packed as a record set. Ask for one with `--set <kind>` (repeatable), or write every record as its own file with `--no-sets`. A `.ndjson` input is checked and packed as the set it is.

`unpack` verifies first, writes nothing from a bundle that fails, and writes only into a new or empty directory.

## Encrypted bundles

To send a bundle by email or another transport you don't trust, encrypt the zip with [age](https://age-encryption.org). By convention the file is named `.zip.age`. Nothing inside changes.

```sh
# A new passphrase is printed: send it by a different channel than the bundle.
npx @legiblerecords/legible bundle pack evidence/ -o evidence.zip.age --passphrase

# Or to an age recipient, with the Rust tool.
legible bundle pack evidence/ -o - | age -r age1... > evidence.zip.age
legible bundle unpack evidence.zip.age -i reader.age.txt -d evidence
```

- Encryption hides the contents, not the file's name, its rough size, or that it was sent.
- Encryption shows the bundle wasn't changed in transit, not who made it. The signature inside says who made it.
- Never put a passphrase on a command line.

Spec: [records.md § Bundles](https://github.com/legiblerecords/spec/blob/main/spec/records.md#bundles).
