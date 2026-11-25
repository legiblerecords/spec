# Schema language

Status: draft. Vectors: [vectors/schema-language.json](../vectors/schema-language.json) and [vectors/schema-language-published.json](../vectors/schema-language-published.json).

Legible Records types are JSON Schema 2020-12. They are written in a short form: a document in [restricted YAML](restricted-yaml.md) that expands to a JSON Schema body, and that a tool can generate back from that body. Readers and validators only need the expanded JSON Schema; the short form is for writing and reviewing.

The short form was first built for Monorail's Track, where it describes table schemas. This document is the general grammar; [§ Published types](#published-types) adds what a Legible Records type needs on top.

## Example

```yaml
type: tech.monorail.controls.control
version: 1
title: control
description: What the organization does to make its commitments true.
fields:
  id: slug
  title: string
  status: known(proposed, active, retired)
  owner: string -- The owning role or person, by name.
  body: string -- What is done, in Markdown.
  scope?: string
  assess_every_months?: integer(1..) -- How long an assessment lasts; 12 when absent.
  due?: date
  contact?: email @user.contact.email.work
```

## Expansion

Expansion takes the short-form text and the schema's **name** (`control` above), and these options:

| Option | Default | Used for |
|---|---|---|
| `common` | `common.schema.json` | where bare names such as `date` point: `<common>#/$defs/<name>` |
| `location` | `{name}.schema.json` | where `<schema>.<name>` points: the location of `<schema>`, then `#/$defs/<name>` |
| `base` | none | the base URL of a published type's `$id`; required when the document has `type` |

A Legible Records type is expanded with `common` set to `https://legiblerecords.org/schemas/org.legiblerecords.common/v1.json` and `base` set to its author's schema URL, such as `https://monorail.tech/schemas/`. The vectors use the defaults unless a case gives `options`.

Expansion returns either a body or every problem in the file ([§ Problems](#problems)).

## Document

A mapping with these keys, all optional. Any other key is a problem.

| Key | Holds | Expands to |
|---|---|---|
| `type` | a type identifier | see [§ Published types](#published-types) |
| `version` | an integer, 1 or more | see [§ Published types](#published-types) |
| `title`, `description` | a string | the same keyword |
| `fields` | a mapping of fields | `"type": "object"`, `properties`, `required` |
| `defs` | a mapping of field values | `$defs` |
| `examples` | a list of mappings | `examples` |
| `json` | a mapping | merged into the body |

`$schema` is set to `https://json-schema.org/draft/2020-12/schema` unless `json` sets it.

## Fields

A key ending in `?` is optional: the `?` is removed from the property name, and the name isn't added to `required`. Every other name is added to `required`, in file order. An empty name, or two keys naming the same property, is a problem.

A field value is a string or a mapping.

In a string, the first ` -- ` ends the type expression, and the rest is the `description`. Before that, trailing `@<label>` tokens are data labels ([§ Type expressions](#type-expressions)).

A mapping has these keys, all optional:

| Key | Holds | Expands to |
|---|---|---|
| `description` | a string | `description` |
| `type` | a type expression; next to `fields`, only `object?` | the expression; `object?` gives `"type": ["object", "null"]` |
| `fields` | a mapping of fields | as at the top level |
| `items` | a field value | `"type": "array"`, `items` |
| `examples` | a list | `examples` |
| `json` | a mapping | merged into the property |

`items` next to `type` or `fields` is a problem. A `json` key that the node's other keys already set is a problem.

## Type expressions

```
union     = postfix ("|" postfix)*
postfix   = primary ("[]" | "?")*
primary   = "(" union ")" | "/" regex "/" | primitive ["(" args ")"]
          | "ref(" kind ("," kind)* ")" | "enum(" value ("," value)* ")"
          | "known(" value ("," value)* ")" | name
primitive = "string" | "integer" | "number" | "boolean" | "object" | "null"
name      = word | word "." word
word      = [A-Za-z_][A-Za-z0-9_.-]*
```

Spaces may separate tokens, but may not come before `[]`, `?` or `(`.

- `string`, `integer`, `number`, `boolean`, `object`, `null`: `{"type": <it>}`, a *bare primitive*.
- `string(<format>)`: `{"type": "string", "format": <format>}`.
- `/<regex>/`: `{"type": "string", "pattern": <regex>}`. `\` escapes the next character and is kept.
- `integer(<min>..<max>)`, `number(<min>..<max>)`: `minimum` and `maximum`, each a JSON number. Either may be left out.
- `ref(<kind>, …)`: `{"$ref": <refString>, "ref": <kind>}`, or the list of kinds when there are several. Each kind is `[a-z][a-z-]*`. `<refString>` is where the name `common.refString` points.
- `enum(<value>, …)`: `enum` with the values in order. A value in double quotes is a JSON string; a JSON number is a number; a value starting with `'`, or `null`, is a problem; anything else is the string as written, trimmed. Commas and parentheses inside double quotes don't split or close. `type` is `string`, `integer` or `number` when every value has it.
- `known(<value>, …)`: an open list. `{"type": "string", "examples": [<value>, …]}`, never `enum`. Values are read as for `enum`, but every value must be a string: a number is a problem.
- `<word>` without a `.`: the name `common.<word>`.
- `<schema>.<name>`: `{"$ref": "<location of schema>#/$defs/<name>"}`, or `{"$ref": "#/$defs/<name>"}` when `<schema>` is the schema being expanded: its given name, or a published type's title ([§ Published types](#published-types)). `<name>` starts with a letter or `_`.
- `<expr>[]`: `{"type": "array", "items": <expr>}`.
- `<expr>?`: when `<expr>` has `type`, `"null"` is added to it (making it a list), and `null` to its `enum` if it has one; otherwise `{"anyOf": [<expr>, {"type": "null"}]}`.
- `<expr> @<label>`: the field holds data of that kind. Expands to `"x-data": ["<label>"]` on the property. Several labels (`@a @b`) give several entries, in order. A label is `[a-z0-9_]+(\.[a-z0-9_]+)*`, normally a key from a data taxonomy. Labels sit after the whole expression and before ` -- `; an `@` anywhere else, or one without a valid label, is a problem (`bad label`). An `@` inside a description is text.
- `<a> | <b> …`: `{"type": [<a>, <b>, …]}` when every part is a bare primitive; otherwise `{"anyOf": [<a>, <b>, …]}`.

Parentheses, `[]` and `?` together nest at most 32 deep.

## Published types

A document with `type` is a published type: a Legible Records type that others will read and write.

- `type` is a type identifier: two or more segments of `[a-z0-9-]+` joined by `.`, such as `tech.monorail.controls.control`. Anything else is a problem.
- `version` is required when `type` is given, and must be an integer of 1 or more. `version` without `type` is a problem.
- `base` must be given as an option. Expanding a published type without it is a problem.

They expand to:

- `"$id": "<base><type>/v<version>.json"`;
- `"type": "object"`, even when the document has no `fields`;
- two properties ahead of the document's own: `"$type": {"const": "<type>"}` and `"version": {"const": <version>}`;
- `"$type"` and `"version"` at the front of `required`.

A field named `$type` or `version` in a published type is a problem.

A published type's `title`, when it is a word without dots (a letter or `_`, then letters, digits, `_` and `-`), also names the schema itself: `risk-study.range` in a type titled `risk-study` is `{"$ref": "#/$defs/range"}`, whatever name the schema was expanded under. So a type refers to its own definitions the same way in any file, and generation writes them that way. A type titled `common` therefore takes bare names such as `date` as its own definitions, which is how `org.legiblerecords.common` refers to itself.

Published types are also checked against [the published subset](rules.md#the-published-subset). That check is a separate step, so the same expansion serves schemas that aren't published.

## Problems

Expansion reports every problem in the file, each with a line, a path and a message.

- The path joins mapping keys with `.`, as written (`fields.owner?`), and list positions as `[n]`.
- The line is the parser's line for that path, or for its nearest parent that has one.
- A type expression problem's message ends with `` in `<expression>` ``.
- A YAML error is one problem, with an empty path.

The vectors fix messages for the cases they cover. An implementation may word other messages its own way, but must report the same path and line.

## Normal form

`normalize(body)` is `body` with `required` lists of strings sorted, `additionalProperties: true` removed, and `$schema` set when missing. The first two apply to the body, and recursively to the members of `properties`, `$defs` and `anyOf`, and to `items`. Other keywords are unchanged.

## Generation

`generate(body, name)` writes the short form of `normalize(body)`, with the same options as expansion. Expanding the result with those options gives `normalize(body)` back, when it fits within restricted YAML's 64 KiB and 32 levels.

- Document keys in the order `type`, `version`, `title`, `description`, `fields`, `defs`, `examples`, `json`. `$schema` is left out when it is the 2020-12 URL.
- A body is written as a published type when it has `$id`, `properties.$type.const` and `properties.version.const` that agree with each other; `type` and `version` come from the consts, and the two properties, their `required` entries and `$id` aren't written again.
- `fields` when the body's `type` is `object` and every property has a short form. Required fields first, then optional ones, each in alphabetical order. `defs` in alphabetical order.
- Each property takes the first of these that expands back to it exactly: a type expression (with ` -- ` and a one-line description); a mapping with `type`; one with `fields`; one with `type` and `json` for the keywords that have no expression syntax; one with `items`; one with only `json`. `description` and `examples` go in the mapping's own keys.
- In a published type, a property that is exactly `{"type": "string", "examples": [<strings>]}`, or the same with `"type": ["string", "null"]`, is written `known(…)` or `known(…)?`. In any other schema it is written as a mapping with `examples`, so generating an existing schema doesn't change.
- Field mapping keys in the order `description`, `type`, `fields`, `items`, `examples`, `json`. `json`, and anything under it, in alphabetical order.
- Each row of `examples` in `fields` order, then other keys in alphabetical order.
- A name `common.<word>` is written `<word>`, unless the word contains `.` or is a primitive, `ref`, `enum` or `known`.
- Non-empty lists of scalars are written in flow style. Strings are quoted only where restricted YAML needs it.
