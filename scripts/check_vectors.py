#!/usr/bin/env python3
"""Check that the test vectors are well formed.

This doesn't run an implementation: it checks the vectors themselves, so a
mistake in them is caught before an implementation is tested against it.

- every case has a unique name and the keys its kind needs;
- every expected body is a valid JSON Schema 2020-12 schema;
- every restricted-YAML case expects either a value or a known error.

Needs: pip install jsonschema
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parent.parent
YAML_ERRORS = {
    "too_large", "too_deep", "multiple_documents", "anchor", "alias", "tag",
    "non_string_key", "duplicate_key", "syntax", "number_range",
}
OPTIONS = {"base", "common", "location"}


def check_schema_language(path, problems):
    data = json.loads(path.read_text())
    names = set()
    for i, case in enumerate(data["cases"]):
        where = f"{path.name} case {i} ({case.get('name')})"
        name = case.get("name")
        if not name or name in names:
            problems.append(f"{where}: missing or duplicate name")
        names.add(name)
        if not isinstance(case.get("schema"), str):
            problems.append(f"{where}: no schema name")
        unknown = set(case.get("options", {})) - OPTIONS
        if unknown:
            problems.append(f"{where}: unknown options {sorted(unknown)}")
        expect = case.get("expect", {})
        if "short" in case:
            if set(expect) not in ({"body"}, {"problems"}):
                problems.append(f"{where}: an expansion case expects exactly body or problems")
            if "body" in expect:
                try:
                    Draft202012Validator.check_schema(expect["body"])
                except SchemaError as err:
                    problems.append(f"{where}: expected body isn't a valid schema: {err.message}")
            for p in expect.get("problems", []):
                if set(p) != {"line", "path", "message"}:
                    problems.append(f"{where}: a problem needs line, path and message")
        elif "body" in case:
            if set(expect) != {"short"}:
                problems.append(f"{where}: a generation case expects short")
            try:
                Draft202012Validator.check_schema(case["body"])
            except SchemaError as err:
                problems.append(f"{where}: input body isn't a valid schema: {err.message}")
        else:
            problems.append(f"{where}: neither short nor body")
    return len(data["cases"])


def check_restricted_yaml(path, problems):
    data = json.loads(path.read_text())
    names = set()
    for i, case in enumerate(data["cases"]):
        where = f"{path.name} case {i} ({case.get('name')})"
        if case.get("name") in names:
            problems.append(f"{where}: duplicate name")
        names.add(case.get("name"))
        if not isinstance(case.get("yaml"), str):
            problems.append(f"{where}: no yaml")
        expect = case.get("expect", {})
        if set(expect) == {"error"}:
            if expect["error"] not in YAML_ERRORS:
                problems.append(f"{where}: unknown error {expect['error']}")
        elif set(expect) != {"value"}:
            problems.append(f"{where}: expects exactly value or error")
    return len(data["cases"])


def main():
    problems = []
    count = 0
    for path in sorted(ROOT.glob("vectors/schema-language*.json")):
        count += check_schema_language(path, problems)
    count += check_restricted_yaml(ROOT / "vectors" / "restricted-yaml.json", problems)
    for p in problems:
        print(f"FAIL {p}")
    print(f"{count} vector cases checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
