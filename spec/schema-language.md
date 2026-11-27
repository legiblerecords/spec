# Schema language

Status: draft. Vectors: [vectors/schema-language.json](../vectors/schema-language.json) and [vectors/schema-language-published.json](../vectors/schema-language-published.json); for checking records against rules, [vectors/rules.json](../vectors/rules.json).

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
| `rules` | a list of rules; only next to `fields` | `allOf` ([§ Rules](#rules)) |
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
| `rules` | a list of rules; only next to `fields` | `allOf` ([§ Rules](#rules)) |
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

## Rules

A rule is a statement about one object that relates two or more of its fields, or the items of one of its lists. `rules` holds a list of rules, each a string, on anything that has `fields`: the document, a field mapping, an `items` mapping, and an entry in `defs`. A rule's field names are the property names of the object it sits on, without the `?`. A rule on an `items` mapping holds for each item.

```yaml
fields:
  status: known(active, revoked)
  subjects?: string[]
  subject_refs?: externalRef[]
  at?: datetime
  on?: date
  revoked_on?: date
  approvals?:
    items:
      fields:
        name: string
        at?: datetime
        on?: date
      rules:
        - one_of(at, on)
rules:
  - one_of(at, on)
  - any_of(subjects, subject_refs)
  - requires(status = revoked, revoked_on)
  - requires(revoked_on, status = revoked)
```

In a published type, `$type` and `version` aren't fields a rule can name.

```
rule = call
call = name "(" arg ("," arg)* ")"
arg  = "not" arg | path "=" value | path "in" "(" value ("," value)* ")" | call | path
path = step ("." step)*
step = name ["[]"]
name = [A-Za-z_][A-Za-z0-9_-]*
```

Spaces may separate tokens, but may not come before `(` after a call's name, or before `[]`. `not` and `in` are separated from what follows them by a space. A `value` is read as `enum`'s values are ([§ Type expressions](#type-expressions)), and ends at a `,` or `)` outside double quotes.

A **field** is a path of one step without `[]`; a **key** is a path without `[]`.

After a rule parses, three checks run, in this order:

1. The call's name is a shape: `one_of`, `at_most_one`, `any_of`, `requires`, `before`, `not_after`, `ascending`, `unique` or `within`.
2. The shape has the arguments it takes: two or more fields for `one_of` and `any_of`; two fields for `at_most_one`, `before` and `not_after`; two conditions for `requires`; a field and a key for `ascending` and `unique`; two paths for `within`. A **condition** is a field, `a = v` or `a in (…)` with `a` a field, `not` and a condition, or a call.
3. A call inside `requires` is `any_of`, with two or more fields.

A rule's **text** is the rule as written, with each run of whitespace outside a double-quoted value replaced by one space and the ends trimmed. Inside a double-quoted value, where `\` escapes the next character, the text is kept as written, so the text and the value it expands to agree. Nothing else changes: `requires(kind in (service, shared),  owner)` has the text `requires(kind in (service, shared), owner)`, `requires(a = "x  y",  b)` has the text `requires(a = "x  y", b)`, and `one_of(a,b)` keeps its text as it is. A value is read from the rule's text, so an unquoted value's inner runs of whitespace are one space: `a = x  y` means `"x y"`. Quote the value to keep the spaces.

### The shapes

A rule takes one of eight shapes. Four are **standard shapes**, which expand to JSON Schema keywords:

| Shape | Holds when |
|---|---|
| `one_of(a, b, …)` | exactly one of the fields is given |
| `at_most_one(a, b)` | not both are given |
| `any_of(a, b, …)` | at least one is given |
| `requires(<when>, <then>)` | whenever `<when>` holds, `<then>` holds |

`<when>` and `<then>` are **conditions**:

| Condition | Holds when |
|---|---|
| `a` | the field is given |
| `a = v` | the field is given and equals `v` |
| `a in (v, w, …)` | the field is given and is one of them |
| `not <condition>` | the condition doesn't hold |
| `any_of(a, b, …)` | at least one is given |

`requires` is the only shape that takes another shape inside it, and only `any_of`.

The other four are **own shapes**, which have no JSON Schema form:

| Shape | Holds when |
|---|---|
| `before(a, b)` | `a` is less than `b`, or either isn't given |
| `not_after(a, b)` | `a` is less than or equal to `b`, or either isn't given |
| `ascending(list, key)` | each item's `key` is greater than the one before it. An item without the key breaks it |
| `unique(list, key)` | no two items have the same `key`. Items without the key are skipped |
| `within(path, path)` | every value at the first path is among the values at the second |

`before` and `not_after` are one shape, with and without equality.

- `before`, `not_after` and `ascending` compare numbers as numbers, dates as dates and datetimes as moments. A field's kind is read from its type expression, by name, with nothing looked up: `integer` and `number`, with or without a range, are numbers; `date` is a date; `datetime` is a datetime. A value that doesn't parse as its field's kind breaks the rule.
- `list` is a field holding a list. `key` is a field of its items, or a dotted path into them.
- In `within`, a path steps into a list's items with `[]`: `within(statements[].estimates[].expert, experts[].id)`.

### Given

A field is **given** when its key is present and its value isn't an empty list or, for a field whose type is a plain string, an empty string.

A field's type is read from its property in the expanded schema, after `json` is merged in: the property of that name on the object the rule sits on.

- It is a **list** when the property's `type` is `"array"`, as `string[]` and a mapping with `items` expand.
- It is a **plain string** when the property's `type` is `"string"`, it has no `format`, `enum` or `const`, and it isn't what `known(…)` expands to: a non-empty `examples` list of strings beside `type`, with no other keyword than `description` and `x-data`. So `string` and `/<regex>/` are plain strings, and so is a mapping with `type: string` and `examples` whose `json` adds `maxLength`.
- Every other field is given when its key is present: `string(<format>)`, a mapping whose `json` sets `format`, `known(…)`, a mapping with `type: string` and `examples` and nothing else, `enum(…)`, `ref(…)`, and a name such as `date`, which is a `$ref`.

### Expansion

Rules expand to an `allOf` list on their object, one **rule member** per rule, in the order written, and nothing else goes in that list. On the document the object is the body; on a field mapping, the property; on an `items` mapping, `items`; on an entry in `defs`, that entry. Every member carries the rule's text in `x-rule`. A standard shape's member also carries its keywords:

| Rule | Member, beside `"x-rule"` |
|---|---|
| `one_of(a, b, …)` | `"oneOf": [G(a), G(b), …]` |
| `at_most_one(a, b)` | `"not": {"allOf": [G(a), G(b)]}` |
| `any_of(a, b, …)` | `"anyOf": [G(a), G(b), …]` |
| `requires(W, T)` | `"if": C(W), "then": C(T)` |
| an own shape | nothing |

`G(a)`, given, depends on the field's expanded property ([§ Given](#given)):

- a list, whose `type` is `"array"`: `{"required": ["a"], "properties": {"a": {"minItems": 1}}}`
- a plain string, whose `type` is `"string"`, with no `format`, `enum` or `const`, and not in `known(…)`'s form: `{"required": ["a"], "properties": {"a": {"minLength": 1}}}`
- anything else: `{"required": ["a"]}`

`C(condition)`:

- `a`: `G(a)`
- `a = v`: `{"required": ["a"], "properties": {"a": {"const": v}}}`
- `a in (v, w, …)`: `{"required": ["a"], "properties": {"a": {"enum": [v, w, …]}}}`
- `not X`: `{"not": C(X)}`
- `any_of(a, b, …)`: `{"anyOf": [G(a), G(b), …]}`

So the second and third rules of the example expand to:

```json
"allOf": [
  { "x-rule": "any_of(subjects, subject_refs)",
    "anyOf": [
      { "required": ["subjects"], "properties": { "subjects": { "minItems": 1 } } },
      { "required": ["subject_refs"], "properties": { "subject_refs": { "minItems": 1 } } } ] },
  { "x-rule": "requires(status = revoked, revoked_on)",
    "if": { "required": ["status"], "properties": { "status": { "const": "revoked" } } },
    "then": { "required": ["revoked_on"] } }
]
```

### Checking a record

A record is checked against each rule member, on each object in the record that the member applies to: the record itself for the document's rules, a field's value for a field mapping's, each item of a list for an `items` mapping's, and each value that refers to an entry in `defs` for that entry's. A standard shape is checked by its keywords, and an own shape by its text. A rule that doesn't hold is one failure, reported as the rule's and not as the keywords that failed inside it, with the JSON pointer of the object the rule sits on (`""` for the record, `/approvals/1` for a rule on the second item of `approvals`) and a message. `unique` and `within` fail once for each offending value, in the order the values first appear; every other rule fails at most once per object.

Failures are ordered by pointer, in document order (an object before the objects inside it), then by the order of the rules on one object. Among sibling members of one object, the order is property name order, by code point; among a list's items, it is index order.

Each shape has one message template. Field names, keys and paths are written as in the rule, without spaces; `<v>`, `<va>` and `<vb>` are values from the record, `<va>` at `a` and `<vb>` at `b`.

| Rule | Message |
|---|---|
| `one_of(a, b)` | `needs exactly one of a and b` |
| `one_of(a, b, c, …)` | `needs exactly one of a, b or c` |
| `at_most_one(a, b)` | `a and b both given` |
| `any_of(a, b, …)` | `needs a or b`, `needs a, b or c` |
| `requires(<when>, <then>)` | `<when> needs <then>`, or `<when> only when <then>` when `<then>` is `a = v` or `a in (…)` and `<when>` is neither, with each condition phrased as below |
| `before(a, b)` | `a <va> isn't before b <vb>` |
| `not_after(a, b)` | `a <va> is after b <vb>` |
| `ascending(list, key)` | `list isn't in order of key` |
| `unique(list, key)` | `more than one item in list has key <v>`, once for each `<v>` |
| `within(path, among)` | `<v> at path isn't among among`, once for each `<v>` |

A condition is phrased by what it holds of, not by the field it names:

| Condition | Phrase |
|---|---|
| `a` | `a` |
| `a = v` | `v` |
| `a in (v, w, …)` | `v or w`, `v, w or x` |
| `not <condition>` | `not` and the condition's phrase: `not v` |
| `any_of(a, b, …)` | `a or b`, `a, b or c` |

So `requires(status = revoked, revoked_on)` gives `revoked needs revoked_on`, `requires(revoked_on, status = revoked)` gives `revoked_on only when revoked`, and `requires(not kind in (service, shared), any_of(person_id, person_email))` gives `not service or shared needs person_id or person_email`. Two names or values are joined by `and` in `one_of` and by `or` elsewhere; three or more are joined by `, ` with `or` before the last, in `one_of` too.

A value, from the record or from a rule, is shown this way:

- A string is shown as written, except that `\`, the C0 controls (U+0000 to U+001F), DEL (U+007F) and the C1 controls (U+0080 to U+009F) are escaped as JSON escapes them: `\\`, `\b`, `\t`, `\n`, `\f`, `\r`, and `\u` with four lowercase hex digits for the others (`\u001b`). So a record's value can't add a line to a checker's output or send a terminal escape.
- A number is shown as JSON writes it: an integer of up to 64 bits as its digits, and any other number as the shortest decimal digits that read back as the same double, with a digit after the point when no exponent is written (`2.5`, `1.0` for `1.0` or `1e0`). Whether and how an exponent is written (`1e+20`) isn't fixed.
- Any other value, which `before`, `not_after`, `unique` and `within` can meet, is shown as JSON without spaces, with an object's members in property name order and DEL and C1 controls escaped as in a string: `{"a":1,"b":[2]}`.

[vectors/rules.json](../vectors/rules.json) fixes the messages.

### Problems with rules

Each of these is a problem ([§ Problems](#problems)):

- `rules` without `fields` beside it (`rules without fields`), or on an object that may be null, one whose `type` is `object?` (`rules on an object that may be null`). The path is the `rules` key.
- `rules` that isn't a list of strings.
- `json` setting `allOf` on an object that has `rules` (`json sets allOf beside rules`). The path is the `allOf` key under `json`.

Each of these is a problem with one rule, reported by the first step that fails: parsing, the three checks, then the rest in order. Its path is the rule's position in the list (`rules[0]`), and its message ends with `` in `<rule>` ``, the rule as written.

- A rule that doesn't fit the grammar (`bad rule`). Only this is `bad rule`; the three checks after parsing have problems of their own.
- A call whose name isn't a shape (`unknown shape <name>`).
- A shape without the arguments it takes, such as `at_most_one(a, b, c)` (`at_most_one takes two fields`).
- A call inside `requires` other than `any_of` (`requires takes only any_of inside it`).
- A field the object doesn't have, or a step of a key or path that isn't a field where it points (`no field <name>`).
- A field whose value may be null (`<name> is nullable`).
- A field compared by `before` or `not_after`, or an `ascending` key, that isn't a number, date or datetime (`before needs numbers, dates or datetimes: <name> is <type expression>`), or two fields of different kinds (`before compares a date with a datetime`, the kinds in the order of the arguments).
- A `list` that isn't a list, or a `[]` step on a field that isn't a list.
- A rule whose text is the same as an earlier rule's on the same object (`rule written twice`), at the later one.

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

A field named `$type` or `version` in a published type is a problem. Neither is a field a rule can name ([§ Rules](#rules)).

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

`normalize(body)` is `body` with `required` lists of strings sorted, `additionalProperties: true` removed, and `$schema` set when missing. The first two apply to the body, and recursively to the members of `properties`, `$defs` and `anyOf`, and to `items`. Other keywords are unchanged: rule members ([§ Rules](#rules)), and the rest of `allOf`, are left as they are, in order.

## Generation

`generate(body, name)` writes the short form of `normalize(body)`, with the same options as expansion. Expanding the result with those options gives `normalize(body)` back, when it fits within restricted YAML's 64 KiB and 32 levels.

- Document keys in the order `type`, `version`, `title`, `description`, `fields`, `rules`, `defs`, `examples`, `json`. `$schema` is left out when it is the 2020-12 URL.
- A body is written as a published type when it has `$id`, `properties.$type.const` and `properties.version.const` that agree with each other; `type` and `version` come from the consts, and the two properties, their `required` entries and `$id` aren't written again.
- `fields` when the body's `type` is `object` and every property has a short form. Required fields first, then optional ones, each in alphabetical order. `defs` in alphabetical order.
- An object written with `fields` that has `allOf` takes `rules` when every entry is exactly what its `x-rule` expands to against those fields ([§ Expansion](#expansion)), `x-rule` included: a line per entry, in order, each the entry's `x-rule`. Any other `allOf` has no short form and goes whole under `json`, so a list that mixes rule members with other entries expands back to itself.
- Each property takes the first of these that expands back to it exactly: a type expression (with ` -- ` and a one-line description); a mapping with `type`; one with `fields` (and `rules`); one with `type` and `json` for the keywords that have no expression syntax; one with `items`; one with only `json`. `description` and `examples` go in the mapping's own keys.
- In a published type, a property that is exactly `{"type": "string", "examples": [<strings>]}`, or the same with `"type": ["string", "null"]`, is written `known(…)` or `known(…)?`. In any other schema it is written as a mapping with `examples`, so generating an existing schema doesn't change.
- Field mapping keys in the order `description`, `type`, `fields`, `rules`, `items`, `examples`, `json`. `json`, and anything under it, in alphabetical order.
- Each row of `examples` in `fields` order, then other keys in alphabetical order.
- A name `common.<word>` is written `<word>`, unless the word contains `.` or is a primitive, `ref`, `enum` or `known`.
- Non-empty lists of scalars are written in flow style. Strings are quoted only where restricted YAML needs it.
