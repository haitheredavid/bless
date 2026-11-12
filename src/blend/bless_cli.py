"""`bless`: supervised live-Blender sessions and direct commands."""

# CLI boundaries turn arbitrary operational failures into concise user errors.
# ruff: noqa: BLE001

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from blend import actions, commands
from blend.sessions import (
    bless_root,
    list_records,
    mcp_config_path,
    new_record,
    read_record,
    record_path,
    validate_session_name,
    write_record,
)
from blend.supervisor import run_supervisor

app = typer.Typer(no_args_is_help=True, help="Bless live Blender session control.")
session_app = typer.Typer(
    no_args_is_help=True, help="Create and stop supervised sessions."
)
view_app = typer.Typer(no_args_is_help=True, help="Set the live viewport view.")
display_app = typer.Typer(no_args_is_help=True, help="Set viewport shading.")
camera_app = typer.Typer(no_args_is_help=True, help="Save and restore thread cameras.")
param_app = typer.Typer(no_args_is_help=True, help="Set live model parameters.")
actions_app = typer.Typer(
    no_args_is_help=True, help="List and run actions.yaml actions."
)
app.add_typer(session_app, name="session")
app.add_typer(view_app, name="view")
app.add_typer(display_app, name="display")
app.add_typer(camera_app, name="camera")
app.add_typer(param_app, name="param")
app.add_typer(actions_app, name="actions")
console = Console()
SessionOption = Annotated[
    str | None, typer.Option("--session", help="Target <model>/<session>.")
]


def _abort(exc: Exception):
    console.print(f"[red]{exc}[/red]")
    raise typer.Exit(1)


@app.command()
def supervisor() -> None:
    """Supervise desired sessions in the foreground (signals leave Blender running)."""
    try:
        run_supervisor()
    except Exception as exc:
        _abort(exc)


@session_app.command("start")
def session_start(
    model: str,
    session: str,
    blend: Annotated[
        Path | None, typer.Option(help="Override the session .blend path.")
    ] = None,
) -> None:
    """Request a model/session Blender runtime."""
    try:
        root = bless_root()
        validate_session_name(session)
        model_dir = root / "models" / model
        if not model_dir.is_dir() or model == "_template":
            raise ValueError(f"model does not exist: {model}")
        blend_path = (
            blend.expanduser().resolve() if blend else model_dir / "model.blend"
        )
        if not blend_path.is_file():
            raise ValueError(f"blend file does not exist: {blend_path}")
        path = record_path(model, session, root)
        if path.exists():
            record = read_record(model, session, root)
            record.desired = "running"
            if record.status in {"stopped", "failed"}:
                record.status = "starting"
                record.pid = None
                record.port = None
                record.last_error = None
            record.blend = str(blend_path.resolve())
        else:
            record = new_record(model, session, blend_path)
        write_record(record, root)
        console.print(path)
    except Exception as exc:
        _abort(exc)


@session_app.command("stop")
def session_stop(model: str, session: str) -> None:
    """Request clean termination of a session's Blender runtime."""
    try:
        record = read_record(model, session)
        record.desired = "stopped"
        write_record(record)
        console.print(record_path(model, session))
    except Exception as exc:
        _abort(exc)


@app.command()
def status(
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Show all session records without requiring the supervisor or Herdr."""
    try:
        rows = [
            {
                "model": record.model,
                "session": record.session,
                "status": record.status,
                "port": record.port,
                "pid": record.pid,
                "last_ping_at": record.last_ping_at,
                "last_snapshot": record.last_snapshot,
            }
            for record in list_records()
        ]
        if as_json:
            print(json.dumps(rows, indent=2))
            return
        table = Table(
            "model", "session", "status", "port", "pid", "last ping", "last snapshot"
        )
        for row in rows:
            table.add_row(
                *(str(row[key]) if row[key] is not None else "-" for key in row)
            )
        console.print(table)
    except Exception as exc:
        _abort(exc)


@app.command("mcp-config")
def mcp_config(model: str, session: str) -> None:
    """Print the canonical per-session agent MCP config path."""
    try:
        read_record(model, session)
        path = mcp_config_path(model, session)
        print(path.resolve())
    except Exception as exc:
        _abort(exc)


@view_app.command("set")
def view_set(view: str, session: SessionOption = None) -> None:
    """Set a preset, model.toml view, or camera:<id>."""
    try:
        console.print_json(data=commands.view_set(view, session))
    except Exception as exc:
        _abort(exc)


@display_app.command("set")
def display_set(mode: str, session: SessionOption = None) -> None:
    """Set wire, solid, material, or render viewport shading."""
    try:
        console.print_json(data=commands.display_set(mode, session))
    except Exception as exc:
        _abort(exc)


@camera_app.command("save")
def camera_save(thread_id: str, session: SessionOption = None) -> None:
    """Save viewport, selection, and current parameters for a thread."""
    try:
        console.print_json(data=commands.camera_save(thread_id, session))
    except Exception as exc:
        _abort(exc)


@camera_app.command("restore")
def camera_restore(thread_id: str, session: SessionOption = None) -> None:
    """Restore a thread's viewport, selection, and parameters."""
    try:
        console.print_json(data=commands.camera_restore(thread_id, session))
    except Exception as exc:
        _abort(exc)


@app.command()
def snapshot(
    camera: Annotated[
        str | None, typer.Option(help="Restore this camera/thread first.")
    ] = None,
    session: SessionOption = None,
) -> None:
    """Capture a unique viewport PNG and update the session record."""
    try:
        print(commands.snapshot(camera, session))
    except Exception as exc:
        _abort(exc)


@param_app.command("set")
def param_set(name: str, value: str, session: SessionOption = None) -> None:
    """Set a validated params.toml Geometry Nodes input live."""
    try:
        console.print_json(data=commands.param_set(name, value, session))
    except Exception as exc:
        _abort(exc)


@app.command("check")
def check(session: SessionOption = None) -> None:
    """Check mesh health of the live Model collection."""
    try:
        report = commands.check(session)
        if not report["objects"]:
            raise RuntimeError("no visible mesh objects in Model")
        table = Table(
            "object", "size", "faces", "tris", "ngons", "issues", "transforms"
        )
        failed = False
        for item in report["objects"]:
            issue_keys = (
                "loose_verts",
                "loose_edges",
                "degenerate_faces",
                "flipped_edges",
            )
            issues = [f"{item[key]} {key}" for key in issue_keys if item[key]]
            issues += ["negative scale"] if item["negative_scale"] else []
            transforms = [
                name
                for name, key in (
                    ("scale", "unapplied_scale"),
                    ("rot", "unapplied_rotation"),
                )
                if item[key]
            ]
            failed |= bool(issues)
            table.add_row(
                item["name"],
                " x ".join(f"{value:.3g}" for value in item["size"]),
                str(item["faces"]),
                str(item["tris"]),
                str(item["ngons"]),
                ", ".join(issues) or "-",
                ", ".join(transforms) or "-",
            )
        console.print(table)
        if failed:
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        _abort(exc)


@actions_app.command("ls")
def actions_list(
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """List validated actions from actions.yaml."""
    try:
        action_file = actions.load_actions()
        if as_json:
            print(
                json.dumps(
                    [
                        action.model_dump(by_alias=True)
                        for action in action_file.actions
                    ],
                    indent=2,
                )
            )
            return
        table = Table("id", "title", "scope", "backend", "kind")
        for action in action_file.actions:
            table.add_row(
                action.id,
                action.title,
                action.scope,
                action.backend or "-",
                action.kind,
            )
        console.print(table)
    except Exception as exc:
        _abort(exc)


@actions_app.command("run")
def actions_run(
    action_id: str,
    args: Annotated[
        list[str] | None, typer.Argument(help="Action inputs as key=value.")
    ] = None,
    session: SessionOption = None,
) -> None:
    """Run a direct action or workflow with key=value inputs."""
    try:
        action_file = actions.load_actions()
        action = action_file.by_id(action_id)
        values = actions.parse_args(action, args or [])
        result = actions.run_action(action_file, action_id, values, session)
        console.print_json(data=result)
    except Exception as exc:
        _abort(exc)


def main() -> None:
    app()
