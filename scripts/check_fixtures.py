#!/usr/bin/env python3
"""Check every fixture against its schema, offline.

fixtures/<type>/v<n>/valid/*.json must validate against schemas/<type>/v<n>.json;
fixtures/<type>/v<n>/invalid/*.json must not. A type of definitions only, such as
common, has fixtures per definition instead: fixtures/<type>/v<n>/<def>/valid/*.json
must validate against that definition, and invalid/*.json must not. Schemas refer to each other by
$id, and are resolved from this repository, never fetched.

Needs: pip install jsonschema referencing
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent


def load_registry():
    resources = []
    for path in sorted(ROOT.glob("schemas/*/v*.json")):
        schema = json.loads(path.read_text())
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def main():
    registry = load_registry()
    failures = 0
    checked = 0
    for version_dir in sorted(ROOT.glob("fixtures/*/v*")):
        type_name = version_dir.parent.name
        schema_path = ROOT / "schemas" / type_name / f"{version_dir.name}.json"
        if not schema_path.exists():
            print(f"FAIL {version_dir.relative_to(ROOT)}: no schema at {schema_path.relative_to(ROOT)}")
            failures += 1
            continue
        schema = json.loads(schema_path.read_text())
        targets = [(version_dir, schema)]
        for def_dir in sorted(d for d in version_dir.iterdir() if d.is_dir() and d.name not in ("valid", "invalid")):
            if def_dir.name not in schema.get("$defs", {}):
                print(f"FAIL {def_dir.relative_to(ROOT)}: {schema_path.name} has no definition {def_dir.name}")
                failures += 1
                continue
            targets.append((def_dir, {"$ref": f"{schema['$id']}#/$defs/{def_dir.name}"}))
        for fixture_dir, target in targets:
            checked, failures = check_dir(fixture_dir, target, registry, checked, failures)
    print(f"{checked} fixtures checked, {failures} failures")
    return 1 if failures else 0


def check_dir(fixture_dir, schema, registry, checked, failures):
    validator = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
    for expect_valid, sub in ((True, "valid"), (False, "invalid")):
        for fixture in sorted((fixture_dir / sub).glob("*.json")):
            checked += 1
            errors = list(validator.iter_errors(json.loads(fixture.read_text())))
            name = fixture.relative_to(ROOT)
            if expect_valid and errors:
                failures += 1
                print(f"FAIL {name}: expected valid, got: {errors[0].message}")
            elif not expect_valid and not errors:
                failures += 1
                print(f"FAIL {name}: expected invalid, but it validated")
    return checked, failures


if __name__ == "__main__":
    sys.exit(main())
