from pathlib import Path

import pytest
from pydantic import ValidationError

from blend.actions import load_actions

ROOT = Path(__file__).resolve().parents[1]


def test_example_actions_load() -> None:
    actions = load_actions(ROOT / "actions.yaml")
    assert actions.by_id("review.pass").backend == "blender"
    assert actions.by_id("display.set").inputs["mode"].values == [
        "wire",
        "solid",
        "material",
        "render",
    ]


def test_duplicate_id_rejected(tmp_path: Path) -> None:
    path = tmp_path / "actions.yaml"
    path.write_text(
        "- {id: view.set, title: One, scope: global, kind: direct}\n"
        "- {id: view.set, title: Two, scope: global, kind: direct}\n"
    )
    with pytest.raises(ValidationError, match="duplicate action ids"):
        load_actions(path)


def test_enum_without_values_rejected(tmp_path: Path) -> None:
    path = tmp_path / "actions.yaml"
    path.write_text(
        "- id: view.set\n  title: View\n  scope: global\n  kind: direct\n"
        "  inputs:\n    view: {type: enum}\n"
    )
    with pytest.raises(ValidationError, match="enum input needs"):
        load_actions(path)


def test_unknown_workflow_step_rejected(tmp_path: Path) -> None:
    path = tmp_path / "actions.yaml"
    path.write_text(
        "- id: review.pass\n  title: Review\n  scope: global\n  kind: workflow\n"
        "  steps:\n    - {action: missing.action}\n"
    )
    with pytest.raises(ValidationError, match="unknown step action"):
        load_actions(path)
