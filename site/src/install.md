---
title: Install
lede: One set of tools, as a command-line program and as a JavaScript package. Both implement the spec and are tested against its vectors.
---

## The command-line tool

`legible` is one static binary. Download the build for your platform from the [releases](https://github.com/legiblerecords/tools/releases), and check it against `SHA256SUMS` from the same release:

| Platform | Archive |
|---|---|
| Linux, x86_64 (static, any distribution) | `legible-x86_64-unknown-linux-musl.tar.gz` |
| Linux, ARM64 (static, any distribution) | `legible-aarch64-unknown-linux-musl.tar.gz` |
| macOS, Apple silicon | `legible-aarch64-apple-darwin.tar.gz` |
| macOS, Intel | `legible-x86_64-apple-darwin.tar.gz` |
| Windows, x86_64 | `legible-x86_64-pc-windows-msvc.zip` |

```sh
T=x86_64-unknown-linux-musl
U=https://github.com/legiblerecords/tools/releases/latest/download
curl -fsSLO "$U/legible-$T.tar.gz"
curl -fsSL "$U/SHA256SUMS" | sha256sum -c --ignore-missing   # macOS: shasum -a 256 -c --ignore-missing
tar -xzf "legible-$T.tar.gz" && ./legible-$T/legible --version
```

If the checksum doesn't match, don't use the binary. Each archive also has build provenance: `gh attestation verify <archive> --repo legiblerecords/tools` checks that it was built by the tools repository's release workflow.

Or build it from source, with Rust 1.89 or later:

```sh
cargo install --git https://github.com/legiblerecords/tools legible
```

## JavaScript

`@legiblerecords/legible` is the same code compiled to WebAssembly. It includes the command for Node, with the schema, record and bundle commands but not feeds, and it can encrypt bundles with [age](https://age-encryption.org) itself. It isn't published to npm yet.

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

## For agents

The [legible-records skill](https://github.com/legiblerecords/tools/blob/main/skills/legible-records/SKILL.md) teaches an agent to turn exports into records and to pack, check and hand over bundles with `legible`: which commands to run and in what order, how to read what `verify` prints, the shared shapes, when to point at a person and when to leave a match unresolved, and what to report. It is kept in the tools repository, beside the tool it describes.

For Claude Code, install it as a personal skill:

```sh
mkdir -p ~/.claude/skills/legible-records
curl -fsSL https://raw.githubusercontent.com/legiblerecords/tools/main/skills/legible-records/SKILL.md \
  -o ~/.claude/skills/legible-records/SKILL.md
```

Or put it in a project's `.claude/skills/legible-records/` to share it with everyone working there. Other agents can read [the same file](https://raw.githubusercontent.com/legiblerecords/tools/main/skills/legible-records/SKILL.md) as instructions. Agents that implement Legible Records, rather than use it, follow the [specification](/spec/records/) instead.
