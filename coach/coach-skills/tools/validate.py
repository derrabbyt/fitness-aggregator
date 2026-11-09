"""Validate the coach skill package.

Checks:
  1. Every schema is a valid JSON Schema (draft 2020-12).
  2. coach-core/params.yaml and every phase params.yaml validate against their schemas.
  3. Example files validate against their schemas (cross-file $refs resolved).
  4. Every skill folder has SKILL.md with name/description frontmatter.
  5. Phase SKILL.md files contain no hard-coded numbers (numbers live in params.yaml).

Usage:  python tools/validate.py            (from the package root)
Requires: pip install jsonschema pyyaml
"""
import json
import pathlib
import re
import sys

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
SKILLS = ROOT / "skills"
EXAMPLES = ROOT / "examples"

errors: list[str] = []


def load_schemas() -> tuple[dict, Registry]:
    schemas = {}
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        schema = json.loads(path.read_text())
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema
    registry = Registry().with_resources(
        (name, Resource.from_contents(s)) for name, s in schemas.items()
    )
    return schemas, registry


def validate(instance, schema_name: str, schemas: dict, registry: Registry, label: str) -> None:
    validator = Draft202012Validator(
        schemas[schema_name], registry=registry, format_checker=FormatChecker()
    )
    for err in validator.iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{label}: {loc}: {err.message}")


def main() -> int:
    schemas, registry = load_schemas()

    # params
    validate(yaml.safe_load((SKILLS / "coach-core/params.yaml").read_text()),
             "core_params.schema.json", schemas, registry, "coach-core/params.yaml")
    for params in sorted(SKILLS.glob("phase-*/params.yaml")):
        validate(yaml.safe_load(params.read_text()), "phase_params.schema.json",
                 schemas, registry, str(params.relative_to(ROOT)))

    # examples: <name>.example.json -> <name>.schema.json
    for ex in sorted(EXAMPLES.glob("*.example.json")):
        schema_name = ex.name.replace(".example.json", ".schema.json")
        if schema_name not in schemas:
            errors.append(f"{ex.name}: no schema {schema_name}")
            continue
        validate(json.loads(ex.read_text()), schema_name, schemas, registry, ex.name)

    # skills
    for skill_dir in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        md = skill_dir / "SKILL.md"
        if not md.exists():
            errors.append(f"{skill_dir.name}: missing SKILL.md")
            continue
        text = md.read_text()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        meta = yaml.safe_load(m.group(1)) if m else None
        if not meta or meta.get("name") != skill_dir.name or not meta.get("description"):
            errors.append(f"{skill_dir.name}: frontmatter needs name == folder and a description")
        if skill_dir.name.startswith("phase-") and skill_dir.name != "phase-start" \
                and skill_dir.name != "phase-review":
            body = text[m.end():] if m else text
            # digits inside `param.keys` are fine; any other digit is a hard-coded number
            for line_no, line in enumerate(body.splitlines(), 1):
                if re.search(r"\d", re.sub(r"`[^`]*`", "", line)):
                    errors.append(f"{skill_dir.name}/SKILL.md:{line_no}: number in prose "
                                  f"(move it to params.yaml): {line.strip()[:80]}")

    if errors:
        print("\n".join(errors))
        print(f"\n{len(errors)} problem(s)")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
