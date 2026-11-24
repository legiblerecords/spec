---
title: CLI
lede: Every legible command. The npm package's command has the same ones, except feeds, and adds age encryption.
---

## Schemas

| Command | Does |
|---|---|
| `legible expand <schema.yaml>` | Expands a short-form schema to JSON Schema |
| `legible generate <schema.json>` | Writes a JSON Schema back as canonical short form |
| `legible lint <schema>` | Checks a published type against the published subset |
| `legible check-compat <old> <new>` | Lists changes that would break readers or writers of the old version |
| `legible validate -s <schema> <record.json>…` | Validates records against their types, chosen by `$type` and `version` |

For a published type, give the base of its `$id` with `--base`. Shared names such as `date` then point at `org.legiblerecords.common`. `validate` never fetches anything: give every schema it needs with `-s`.

## Bundles

| Command | Does |
|---|---|
| `legible bundle pack <file or dir>… -o <bundle.zip>` | Packs records and attachments into a bundle, with record sets for large kinds |
| `legible bundle verify <bundle>` | Checks hashes, file list, references and signature |
| `legible bundle unpack <bundle> -d <dir>` | Verifies, then writes the files into a new or empty directory |
| `legible bundle sign <bundle.zip> -k <key.json> -o <signed.zip>` | Signs a bundle's manifest as stored |

`pack` writes a kind with more than 1,000 records as a record set. `--set <kind>` (repeatable) asks for one, and `--no-sets` writes every record as its own file.

`verify` and `unpack` take `--pin <publisher>/<id>=<public_key>` and `--key-set <keys.json>`, each repeatable, and `-i <identity>` to decrypt.

## Keys

| Command | Does |
|---|---|
| `legible keys new --publisher <domain> --id <id> -o <key.json>` | Makes a signing key and prints its key-set entry |
| `legible keys sign <keys.json> -k <key.json> -o <keys.sig>` | Endorses a key set |

## Feeds

| Command | Does |
|---|---|
| `legible feed publish <dir> --feed <id> --stream <id> …` | Packs records into a stream of a feed in a directory |
| `legible feed check <connection.json>` | Polls a feed and reports each stream's outcome. Keeps nothing. |
| `legible feed pull <connection.json> --state <dir> --out <dir>` | Polls a feed, writes accepted bundles, and keeps reader state |

## Exit status

| Status | Means |
|---|---|
| 0 | Everything passed |
| 1 | The input has problems |
| 2 | The tool couldn't run |
