---
title: Rules for types
lede: These rules keep records written today readable by tools written later, and the reverse.
---

## The published subset

A published type's expanded schema doesn't use:

- `if`, `then`, `else`, `not`, `dependentSchemas` or `dependentRequired`;
- `oneOf`, or `anyOf` other than for a value that may be null;
- `additionalProperties: false`, at any level: readers must accept fields they don't know.

A type with variants uses an explicit `kind` field, with optional fields for each kind. Use `enum` only for a set that will never grow, and `known(…)` for everything else.

```sh
legible lint control.json --base https://monorail.tech/schemas/
```

## Numbers, dates and units

- Put the unit in the field name or its description: `loss` with a record-level `currency`, `events_per_year`, `one_in_years`.
- Probabilities are numbers from 0 to 1.
- Dates without a time are `string(date)`. Moments are `string(date-time)` with an offset.
- Money is in units of one ISO 4217 currency, named once in the record.

## Compatible changes

Within a major version, a new schema may only:

- add an optional field;
- add a value to a `known(…)` list;
- relax a constraint: a wider range, a longer maximum, allowing null;
- change descriptions and examples.

Anything else needs a new major version: removing or renaming a field, making a field required, narrowing a range, changing a field's type, or turning a `known(…)` list into an `enum`. A change in what a field *means* is a new type.

```sh
legible check-compat control-v1-old.json control-v1-new.json
```

## Lenses

A new major version should ship with a lens from the previous one, when the change can be written with these operations from [Cambria](https://inkandswitch.com/cambria):

| Operation | Does |
|---|---|
| rename | Renames a field |
| add, remove | Adds or removes a field, with a default for the other direction |
| hoist, plunge | Moves a field out of or into a nested object |
| wrap, head | Turns a value into a one-item list, or a list into its first item |
| convert | Maps values, such as `"open"` to `true` |

## Conformance

Every published type ships with fixtures: records a conforming reader must accept, and records it must reject, each named for the reason. An implementation may say it supports a type only if it passes that type's fixtures.

Spec: [rules.md]({{ site.spec }}/blob/main/spec/rules.md).
