---
title: Install
lede: One set of tools, in two forms. Both implement the spec and are tested against its vectors.
---

> Neither is released yet.

## The command-line tool

`legible` is written in Rust:

```sh
cargo install --git https://github.com/legiblerecords/tools legible
legible --help
```

## JavaScript

`@legiblerecords/legible` is the same code compiled to WebAssembly. It includes the command for Node, which can also encrypt bundles with [age](https://age-encryption.org) itself:

```sh
npx @legiblerecords/legible@0.1.0 --help
```

Or use it as a library:

```js
import { expand, lint } from "@legiblerecords/legible";

const result = expand(text, "risk-appetite", { base: "https://monorail.tech/schemas/" });
if (result.ok) {
  console.log(lint(result.body)); // [] when it's within the published subset
} else {
  for (const p of result.problems) console.error(`${p.line}: ${p.path}: ${p.message}`);
}
```

In a browser, call `await init()` once before using it.

## Exit status

| Status | Means |
|---|---|
| 0 | Everything passed |
| 1 | The input has problems |
| 2 | The tool couldn't run |
