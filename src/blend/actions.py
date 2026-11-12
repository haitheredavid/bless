"""Validated actions.yaml loader and direct/workflow dispatcher."""

import re
import subprocess
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from blend import commands
from blend.sessions import bless_root


class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["enum", "number", "text", "thread", "camera", "param", "none"]
    values: list[str] | None = None
    optional: bool = False

    @model_validator(mode="after")
    def validate_values(self):
        if self.type == "enum" and not self.values:
            raise ValueError("enum input needs non-empty values")
        if self.type != "enum" and self.values is not None:
            raise ValueError("values is only valid for enum inputs")
        return self


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    with_: dict[str, object] = Field(default_factory=dict, alias="with")
    stop_on_fail: bool = False


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)*$")
    title: str
    scope: str
    backend: Literal["blender", "threejs"] | None = None
    kind: Literal["direct", "agent", "workflow"]
    inputs: dict[str, ActionInput] = Field(default_factory=dict)
    steps: list[WorkflowStep] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_action(self):
        if self.scope not in {"global", "blender", "threejs"} and not re.fullmatch(
            r"model:[a-z0-9][a-z0-9-]*", self.scope
        ):
            raise ValueError("scope must be global, blender, threejs, or model:<name>")
        if self.backend is None:
            self.backend = "threejs" if self.scope == "threejs" else "blender"
        if self.kind == "workflow" and not self.steps:
            raise ValueError("workflow action needs steps")
        if self.kind != "workflow" and self.steps:
            raise ValueError("steps are only valid for workflow actions")
        return self


class ActionFile(BaseModel):
    actions: list[Action]

    @model_validator(mode="after")
    def validate_references(self):
        ids = [action.id for action in self.actions]
        if len(ids) != len(set(ids)):
            duplicates = sorted({item for item in ids if ids.count(item) > 1})
            raise ValueError(f"duplicate action ids: {', '.join(duplicates)}")
        known = set(ids)
        for action in self.actions:
            for step in action.steps:
                if step.action not in known:
                    raise ValueError(
                        f"{action.id}: unknown step action {step.action!r}"
                    )
                target = next(item for item in self.actions if item.id == step.action)
                if unknown := set(step.with_) - set(target.inputs):
                    raise ValueError(
                        f"{action.id}: unknown inputs for {step.action}: "
                        f"{', '.join(sorted(unknown))}"
                    )
                for name, value in step.with_.items():
                    spec = target.inputs[name]
                    if spec.type == "enum" and value not in (spec.values or []):
                        raise ValueError(
                            f"{action.id}: {step.action}.{name} must be one of "
                            f"{', '.join(spec.values or [])}"
                        )
        return self

    def by_id(self, action_id: str) -> Action:
        try:
            return next(action for action in self.actions if action.id == action_id)
        except StopIteration as exc:
            raise LookupError(f"unknown action {action_id!r}") from exc


def load_actions(path: Path | None = None, root: Path | None = None) -> ActionFile:
    path = path or (root or bless_root()) / "actions.yaml"
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, list):
        raise TypeError("actions.yaml must contain a list")
    return ActionFile(actions=raw)


def parse_args(action: Action, pairs: list[str]) -> dict[str, object]:
    values: dict[str, object] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator or not key:
            raise ValueError(f"action argument must be key=value: {pair!r}")
        if key in values:
            raise ValueError(f"action argument supplied twice: {key}")
        values[key] = value
    unknown = set(values) - set(action.inputs)
    if unknown:
        raise ValueError(
            f"unknown inputs for {action.id}: {', '.join(sorted(unknown))}"
        )
    missing = [
        name
        for name, spec in action.inputs.items()
        if not spec.optional and name not in values and spec.type != "none"
    ]
    if missing:
        raise ValueError(f"missing inputs for {action.id}: {', '.join(missing)}")
    for name, value in list(values.items()):
        spec = action.inputs[name]
        if spec.type == "enum" and value not in (spec.values or []):
            raise ValueError(f"{name} must be one of {', '.join(spec.values or [])}")
        if spec.type == "number":
            float(str(value))
    return values


def run_action(
    action_file: ActionFile,
    action_id: str,
    values: dict[str, object],
    selector: str | None = None,
    root: Path | None = None,
):
    action = action_file.by_id(action_id)
    if action.kind == "agent":
        raise RuntimeError(
            "agent action dispatch is not available from the Bless CLI yet"
        )
    if action.kind == "workflow":
        results = []
        for step in action.steps:
            merged = {**values, **step.with_}
            child = action_file.by_id(step.action)
            child_values = {
                key: value for key, value in merged.items() if key in child.inputs
            }
            try:
                results.append(
                    run_action(action_file, step.action, child_values, selector, root)
                )
            except Exception as exc:
                if step.stop_on_fail:
                    raise
                results.append({"action": step.action, "error": str(exc)})
        return results
    return _run_direct(action.id, values, selector, root)


def _run_direct(
    action_id: str, values: dict[str, object], selector: str | None, root: Path | None
):
    if action_id == "view.set":
        return commands.view_set(str(values["view"]), selector, root)
    if action_id == "display.set":
        return commands.display_set(str(values["mode"]), selector, root)
    if action_id == "camera.restore":
        return commands.camera_restore(str(values["thread"]), selector, root)
    if action_id == "snapshot":
        path = commands.snapshot(
            str(values["camera"]) if values.get("camera") else None, selector, root
        )
        return {"snapshot": str(path)}
    if action_id == "param.set":
        return commands.param_set(
            str(values["name"]), str(values["value"]), selector, root
        )
    if action_id == "mesh.check":
        return commands.check(selector, root)
    if action_id == "print.pack":
        target = commands.resolve_target(selector, root)
        process = subprocess.run(
            ["uv", "run", "blend", "print-pack", target.record.model],
            cwd=root or bless_root(),
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode:
            raise RuntimeError(process.stderr.strip() or process.stdout.strip())
        return {"output": process.stdout.strip()}
    raise RuntimeError(
        f"direct action {action_id!r} has no command-layer implementation"
    )
