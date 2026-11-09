"""The coach-skills package ships inside the coach project: its validator is
green, and the coach reads skills, params and schemas from it."""

import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "coach-skills"


def test_skills_validator_passes():
    result = subprocess.run(
        [sys.executable, str(PACKAGE / "tools" / "validate.py")], capture_output=True, text=True, timeout=60
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "all checks passed" in result.stdout


def test_coach_reads_its_skills_package(coach):
    assert coach.skills.skill("coach-core").startswith("---\nname: coach-core\n")


def test_phase_params_override_core_params(coach):
    params = coach.skills.params("reverse_bulk")

    assert params["phase_id"] == "reverse_bulk"
    assert params["macros"]["protein_g_per_kg"] == 2.0  # phase key
    assert params["decisions"]["max_change_kcal"] == 200  # core key, kept
    assert params["data"]["sync_max_age_hours"] == 36


def test_core_params_without_a_phase(coach):
    params = coach.skills.params()

    assert "phase_id" not in params
    assert params["measurements"]["waist_every_weeks"] == 2


def test_example_facts_validate_against_their_schema(coach):
    import json

    example = json.loads((PACKAGE / "examples" / "weekly_facts.example.json").read_text())

    assert coach.skills.errors(example, "weekly_facts") == []
    assert coach.skills.errors({"schema_version": 1}, "weekly_facts") != []
