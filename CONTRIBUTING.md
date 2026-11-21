# Contributing

Legible Records is a draft. Issues are welcome: questions, problems with the spec, and types you'd like to publish. Pull requests are welcome too, but for anything beyond a fix, open an issue first so we can agree on the change.

## Sign your commits off

Contributions are accepted under the [Developer Certificate of Origin](https://developercertificate.org/). Add a `Signed-off-by` line to every commit (`git commit -s`), certifying that you wrote the change or have the right to contribute it under the project's license.

## Changing the spec

- A change to a published type's schema must follow [the compatibility rules](spec/rules.md#compatible-changes), and comes with fixtures: at least one valid record that uses the change, and an invalid one when the change adds a constraint.
- Run `python scripts/check_fixtures.py` before opening a pull request. CI runs it too.
- Keep the expanded `v<n>.json` and the short-form `v<n>.yaml` of a schema in step. Until the short-form tools are published here, the JSON is written by hand from the YAML.

## Publishing your own types

You don't need to contribute here to publish types. Publish them under a domain you control, following the spec, with your own fixtures. Open an issue if you'd like them listed.
