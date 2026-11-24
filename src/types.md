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

## Sensitivity labels

A schema can say what kind of data a field holds, with a label from a data taxonomy: `@user.contact.email` in the short form, `x-data` in JSON Schema. Labels tell a reader, a publisher or an agent how to handle a field before reading its value. Types say which taxonomy they use.

Spec: [records.md](https://github.com/legiblerecords/spec/blob/main/spec/records.md).
