"""The coach-skills package (coach/coach-skills): skills, params and schemas,
read at runtime. See coach-skills/README.md for which job loads what."""

import copy
import json
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "coach-skills"


class SkillsPackage:
    def __init__(self, root: Path | str = DEFAULT_ROOT):
        self.root = Path(root)

    def skill(self, name: str) -> str:
        """SKILL.md of a skill folder, e.g. "coach-core", "phase-reverse-bulk"."""
        return (self.root / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    def phase_skill_name(self, phase_id: str) -> str:
        """Skill folder of a phase id, e.g. reverse_bulk -> phase-reverse-bulk."""
        for path in sorted((self.root / "skills").glob("phase-*/params.yaml")):
            if _yaml(path).get("phase_id") == phase_id:
                return path.parent.name
        raise KeyError(f"no phase skill with phase_id {phase_id!r}")

    def phase_ids(self) -> list[str]:
        return [_yaml(path).get("phase_id") for path in sorted((self.root / "skills").glob("phase-*/params.yaml"))]

    def phase_params(self, phase_id: str) -> dict[str, Any]:
        """The phase's own params.yaml (not merged)."""
        return _yaml(self.root / "skills" / self.phase_skill_name(phase_id) / "params.yaml")

    def undecided(self, phase_id: str) -> list[str]:
        """Key paths in the phase's params.yaml marked TO DECIDE (draft phases
        must not start while any are left)."""
        path = self.root / "skills" / self.phase_skill_name(phase_id) / "params.yaml"
        stack: list[tuple[int, str]] = []
        found = []
        for line in path.read_text(encoding="utf-8").splitlines():
            body = line.split("#", 1)[0]
            if ":" not in body or not body.strip() or body.strip().startswith("-"):
                continue
            indent = len(body) - len(body.lstrip())
            key = body.strip().split(":", 1)[0].strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent, key))
            if "TO DECIDE" in line:
                found.append(".".join(k for _, k in stack))
        return found

    def params(self, phase_id: str | None = None) -> dict[str, Any]:
        """coach-core params, merged with the phase's params (phase wins on equal
        key paths). A fresh copy each call."""
        merged = copy.deepcopy(_yaml(self.root / "skills" / "coach-core" / "params.yaml"))
        if phase_id is not None:
            phase = _yaml(self.root / "skills" / self.phase_skill_name(phase_id) / "params.yaml")
            _merge(merged, copy.deepcopy(phase))
        return merged

    def schema(self, name: str) -> dict[str, Any]:
        """A schema by name, e.g. "weekly_facts" (schemas/weekly_facts.schema.json)."""
        return self._schemas()[f"{name}.schema.json"]

    def errors(self, instance: Any, schema: str) -> list[str]:
        """Validation errors of `instance` against a schema; [] when valid."""
        validator = Draft202012Validator(self.schema(schema), registry=self._registry(), format_checker=FormatChecker())
        return [
            f"{'/'.join(str(p) for p in err.absolute_path) or '(root)'}: {err.message}"
            for err in validator.iter_errors(instance)
        ]

    def _schemas(self) -> dict[str, dict[str, Any]]:
        return _load_schemas(self.root / "schemas")

    def _registry(self) -> Registry:
        return Registry().with_resources(
            (name, Resource.from_contents(schema)) for name, schema in self._schemas().items()
        )


@cache
def _load_schemas(folder: Path) -> dict[str, dict[str, Any]]:
    return {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.schema.json"))}


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
