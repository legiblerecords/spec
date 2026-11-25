---
title: Types
lede: Legible Records defines how types work, not which types exist.
---

Anyone publishes types under a domain they control, in reverse order. Monorail's controls type is `tech.monorail.controls.control`, published at `https://monorail.tech/schemas/`. A file is then "a Legible Record of type `tech.monorail.controls.control`."

## Type identifiers

A type identifier is a domain its author controls, reversed, followed by the type's name. Segments are lowercase letters, digits and hyphens.

- Types are grouped by what they describe, not by the app that writes them, so a type keeps its name when another app starts writing it.
- A published identifier never changes. A breaking change is a new major version. A change in meaning is a new type.
- The schema is at the `$id` its author publishes, conventionally `https://<domain>/schemas/<type>/v<major>.json`.

Definitions every type shares, such as `date`, `slug` and `refString`, are under `org.legiblerecords.common`, at `https://legiblerecords.org/schemas/`.

## References

One record refers to another with a string `kind:key`. `kind` is the referenced type's short name (its `title`) and `key` is that record's `id`. A reference may name part of a record after `#`.

```text
control:mfa-company-accounts
policy:access-control#scope
```

A reference resolves within the records it travels with: a bundle, or a directory a tool is reading.

A reference to an attachment is an object:

```json
{ "sha256": "…", "name": "access-review-q3.pdf", "media_type": "application/pdf" }
```

## Pointing at records elsewhere

A `kind:key` reference must resolve in the records it travels with. Three shared definitions point at things that don't. A reader never resolves them inside a bundle, so none of them can make a bundle fail.

### External references

`externalRef` names a record that travels elsewhere, in another stream or from another publisher:

```json
{ "type": "tech.monorail.policy.document", "key": "access-control",
  "publisher": "acme.example", "revision": 3, "sha256": "…" }
```

- `type` is the record's full `$type`, not the short name a `kind:key` reference uses. `key` is its `id`.
- `publisher` says whose record it is. A writer leaves it out only for its own records, and only inside a signed bundle or a feed, where the publisher is known.
- `revision` is for types that number their own revisions, such as a policy. It isn't the type's `version`.
- `sha256` is the record's [content hash](#content-lines), pinning exactly what it said.

A reader that holds the target resolves the reference. It shows one it can't resolve as unresolved, and says so when it holds different content under that key.

### Identifiers

`identifier` is something's id in one system:

```json
{ "system": "github", "id": "acme/api" }
```

The two halves together are the key, and match only when both are exactly equal. `system` is lowercase. A misspelt system matches nothing, and a reader shows that rather than matching something else.

Each system name means one kind of id, so two publishers describing the same thing write the same identifier. Where a system has a stable id and a changeable name, the system's own name means the stable id:

| System | `id` is | Example |
|---|---|---|
| `github` | For a person or account, the numeric user id; for a repository, `owner/name` | `4183920`, `acme/api` |
| `github-login` | A GitHub login | `ana-lima-acme` |
| `gitlab` | As for `github` | `1290331`, `acme/tools` |
| `okta`, `entra`, `google` | The directory's user id, not the sign-in name | `00u1ab2cd3` |
| `serial` | A device's serial number, as printed | `C02XK1ABCD` |

### Person matches

`personMatch` is what a publisher knows about the person a record is about, when it doesn't know the reader's key for them:

```json
{ "emails": ["ana@acme.example"], "identifiers": [{ "system": "okta", "id": "00u1ab2cd3" }], "name": "Ana Lima" }
```

- It has `emails` or `identifiers`, or both.
- A reader matches identifiers first. Only when no identifier matches anyone does it compare emails, case-insensitively.
- A match to no one, or to more than one person, is left unresolved and shown to a person. A reader never chooses between candidates.
- `name` is for the people resolving a match. It is never matched on.

## Content lines

A record's **content line** is its canonical JSON line, as in a [record set](/bundles/#record-sets), with the top-level `produced_by` and `source` removed. Its SHA-256, in lowercase hex, is the record's **content hash**.

- Republishing a record from a new build or a later export keeps its hash. Changing anything else the record says changes it.
- The hash is over the canonical form, not the bytes of a `.json` file, which can differ in whitespace from one writer to another.
- A record with no canonical form has no content hash, and tools refuse it: one that isn't an object, repeats a key, holds an integer a double can't hold exactly, or holds a lone surrogate.

```sh
$ legible record hash access-control.json
3f1c…e9a2  access-control.json
```

## Sensitivity labels

A schema can say what kind of data a field holds, with a label from a data taxonomy: `@user.contact.email` in the short form, `x-data` in JSON Schema. Labels tell a reader, a publisher or an agent how to handle a field before reading its value. Types say which taxonomy they use.

The rules in full: [Records and bundles](/spec/records/), from [§ A record](/spec/records/#a-record) to [§ Content lines](/spec/records/#content-lines).
