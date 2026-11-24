---
title: Bundles
lede: Several records, with or without attachments, travel together as a bundle. A bundle is a directory, or a zip of one.
---

```text
manifest.json
manifest.sig          (optional)
records/<kind>/<key>.json
files/<sha256>
```

`manifest.json` is itself a record, of type `org.legiblerecords.bundle`. It lists every file with its path and SHA-256, and for records their `$type` and `version`. `manifest.sig` is the only file the manifest doesn't list.

## What a reader checks

- Every file's hash matches the manifest.
- Every file the manifest lists is present, and every file present is listed, except `manifest.sig`.
- Every reference resolves to a record or attachment in the bundle.
- `published_at`, when present, is no more than 24 hours after the reader's clock.

Any failure is an error, not a warning: in a security record, a broken link is usually the thing that matters. The reader returns `bad_bundle`.

Before reading any entry, a reader refuses a zip with two entries of the same name, or a name that starts with `/`, contains `\`, or has a `.` or `..` segment.

## Packing and verifying

```sh
legible bundle pack evidence/ -s control.yaml -o evidence.zip
legible bundle verify evidence.zip -s control.yaml
legible bundle unpack evidence.zip -d evidence
```

`pack` treats a `.json` file with `$type` and `version` as a record. Anything else is an attachment, stored by its SHA-256. The reference to put in a record is printed to stderr. The same files always pack to the same bytes.

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
