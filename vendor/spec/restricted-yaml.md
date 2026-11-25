# Restricted YAML

Status: draft. Vectors: [vectors/restricted-yaml.json](../vectors/restricted-yaml.json).

Short-form schemas are written in a deliberately small subset of YAML. A parser returns JSON values, and reports a failure as a reason, with a 1-based line and column where it has one.

## Limits

- Text over 65,536 UTF-8 bytes fails as `too_large`, before parsing.
- Nesting deeper than 32 collections fails as `too_deep`. A top-level mapping or list is depth 1.

## Documents

- Empty input is `null`.
- One document is allowed, with or without an explicit `---`. More than one fails as `multiple_documents`.

## What isn't allowed

- Anchors, aliases and explicit tags fail as `anchor`, `alias` and `tag`. The first one in document order is reported.
- Mapping keys must be scalar strings. Plain `true`, `false`, `null`, numbers, and complex keys fail as `non_string_key`. A quoted `"1"` is a string, and allowed.
- A key that appears twice in one mapping fails as `duplicate_key`.
- Anything else the parser can't read fails as `syntax`.

Comments are ignored.

## Scalars

Quoted scalars and block scalars (`|`, `>`) are strings.

A plain scalar is:

- `true`, `false` or `null` when it is exactly that word;
- a number when it matches the whole JSON number grammar:

  ```text
  -?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?
  ```

- otherwise a string. So `no`, `yes`, `~`, `0x1F`, `1_000`, `.5` and `inf` are all strings, unlike in YAML 1.1.

An integer with no fraction or exponent outside ±(2^53 − 1) fails as `number_range`, and so does a number that isn't finite as a 64-bit float, such as `1e400`.

## Why restricted

Schemas are small, reviewed by people, and parsed by many tools. Removing anchors, tags and YAML 1.1's implicit typing means every parser reads the same file the same way, and a file can't hide structure from the person reviewing it.
