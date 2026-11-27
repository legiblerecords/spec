# Rules for published types

Status: draft.

These rules keep records written today readable by tools written later, and the reverse.

## The published subset

A published type's expanded schema doesn't use:

- `else`, `dependentSchemas` or `dependentRequired`;
- `if`, `then`, `not` or `oneOf`, other than inside a rule member;
- `anyOf`, other than inside a rule member or for a value that may be null;
- `allOf`, other than inside a rule member, or to hold rule members and nothing else;
- `additionalProperties: false`, at any level: readers must accept fields they don't know.

A **rule member** is an entry of an `allOf` list that has an `x-rule` and is exactly what that rule expands to ([schema language § Rules](schema-language.md#rules)): its other keywords are the rule's expansion and nothing more. Checking the subset includes checking each rule member against its rule.

A type with variants uses an explicit `kind` field, with optional fields for each kind, rather than `oneOf`.

Use `enum` only for a set that will never grow. Use `known(…)` for everything else.

## Numbers, dates and units

- Put the unit in the field name or its description: `loss` with a record-level `currency`, `events_per_year`, `one_in_years`.
- Probabilities are numbers from 0 to 1.
- Dates without a time are `string(date)`; moments are `string(date-time)` with an offset.
- Money is in units of one ISO 4217 currency named once in the record.

## Compatible changes

Within a major version, a new schema may only:

- add an optional field;
- add a value to a `known(…)` list;
- relax a constraint: a wider range, a longer maximum, allowing null;
- remove a rule;
- change descriptions and examples.

Anything else needs a new major version: removing or renaming a field, making a field required, narrowing a range, changing a field's type, adding a rule, or turning a `known(…)` list into an `enum`.

Rules are compared by their `x-rule` text: a rule whose text changes is one rule removed and another added.

A change in what a field *means* is not a new version but a new type.

## Lenses

A new major version should ship with a lens from the previous one when the change can be written as a sequence of these operations, from [Cambria](https://inkandswitch.com/cambria):

| Operation | Does |
|---|---|
| rename | renames a field |
| add, remove | adds or removes a field, with a default for the other direction |
| hoist, plunge | moves a field out of or into a nested object |
| wrap, head | turns a value into a one-item list, or a list into its first item |
| convert | maps values, such as `"open"` to `true` |

Each lens has fixtures for both directions. A change that can't be written this way, such as one that needs a statistical fit, gets a documented one-way conversion instead.

## Conformance

Every published type ships with fixtures: records that a conforming reader must accept and records it must reject, each named for the reason. An implementation may say it supports a type only if it passes that type's fixtures.
