"""`bless`: supervised live-Blender sessions and direct commands."""

# CLI boundaries turn arbitrary operational failures into concise user errors.
# ruff: noqa: BLE001

import json
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.table import Table

from blend import actions, commands, graph, interaction
from blend import model as models
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
graph_app = typer.Typer(no_args_is_help=True, help="Import and build prompt graphs.")
prompt_app = typer.Typer(no_args_is_help=True, help="Record and correct prompt data.")
pin_app = typer.Typer(
    no_args_is_help=True, help="Store anchored model discussion pins."
)
lasso_app = typer.Typer(
    no_args_is_help=True, help="Preview and apply screen-space selections."
)
app.add_typer(session_app, name="session")
app.add_typer(view_app, name="view")
app.add_typer(display_app, name="display")
app.add_typer(camera_app, name="camera")
app.add_typer(param_app, name="param")
app.add_typer(actions_app, name="actions")
app.add_typer(graph_app, name="graph")
app.add_typer(prompt_app, name="prompt")
app.add_typer(pin_app, name="pin")
app.add_typer(lasso_app, name="lasso")
console = Console()
SessionOption = Annotated[
    str | None, typer.Option("--session", help="Target <model>/<session>.")
]


def _abort(exc: Exception):
    console.print(f"[red]{exc}[/red]")
    raise typer.Exit(1)


def _json_abort(exc: Exception):
    print(json.dumps({"error": str(exc)}))
    raise typer.Exit(1)


def _models(ref: str | None, all_models: bool) -> list[models.Model]:
    root = bless_root()
    base = root / "models"
    if all_models:
        if ref:
            raise ValueError("MODEL and --all are mutually exclusive")
        return models.list_all(base)
    if not ref:
        raise ValueError("provide MODEL or --all")
    return [models.resolve(ref, base)]


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


@session_app.command("restart")
def session_restart(model: str, session: str) -> None:
    """Ask the supervisor to terminate and relaunch a runtime."""
    try:
        record = read_record(model, session)
        if record.desired != "running":
            raise RuntimeError(f"session {model}/{session} is stopped")
        record.status = "restarting"
        record.last_error = "restart requested"
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


@camera_app.command("ls")
def camera_list(
    model: str,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """List saved thread camera records."""
    try:
        records = commands.camera_list(model)
        if as_json:
            print(json.dumps(records))
        else:
            for record in records:
                console.print(record["thread"])
    except Exception as exc:
        if as_json:
            _json_abort(exc)
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


@app.command()
def state(
    model: str,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Return the complete Herdr-facing state for one model."""
    try:
        root = bless_root()
        models.resolve(model, root / "models")
        payload = {
            "model": model,
            "root": str(root),
            "sessions": [
                record.model_dump(by_alias=True)
                for record in list_records(root)
                if record.model == model
            ],
            "latest_snapshot": interaction.latest_sidecar(root, model),
            "pins": interaction.load_pins(root, model),
            "cameras": interaction.camera_records(root, model),
        }
        if as_json:
            print(json.dumps(payload))
        else:
            console.print_json(data=payload)
    except Exception as exc:
        if as_json:
            _json_abort(exc)
        _abort(exc)


def _parse_uv(value: str) -> tuple[float, float]:
    try:
        u, v = (float(part) for part in value.split(",", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("--uv must be <u>,<v>") from exc
    return u, v


@pin_app.command("add")
def pin_add(
    session: Annotated[
        str, typer.Option("--session", help="Target <model>/<session>.")
    ],
    uv: Annotated[str, typer.Option("--uv", help="Normalized top-left u,v.")],
    thread: Annotated[str, typer.Option("--thread")],
    note: Annotated[str | None, typer.Option("--note")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Raycast a snapshot coordinate and save an anchored pin."""
    try:
        pin = commands.pin_add(session, _parse_uv(uv), thread, note)
        if as_json:
            print(json.dumps(pin))
        else:
            console.print_json(data=pin)
    except Exception as exc:
        if as_json:
            _json_abort(exc)
        _abort(exc)


@pin_app.command("ls")
def pin_list(
    model: str,
    snapshot: Annotated[Path | None, typer.Option("--snapshot")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """List pins, optionally projected onto a snapshot."""
    try:
        pins = interaction.pins_with_uv(bless_root(), model, snapshot)
        if as_json:
            print(json.dumps(pins))
        else:
            console.print_json(data=pins)
    except Exception as exc:
        if as_json:
            _json_abort(exc)
        _abort(exc)


@pin_app.command("rm")
def pin_remove(model: str, pin_id: str) -> None:
    """Delete a stored pin."""
    try:
        interaction.remove_pin(bless_root(), model, pin_id)
    except Exception as exc:
        _abort(exc)


@lasso_app.command("preview")
def lasso_preview(
    session: Annotated[
        str, typer.Option("--session", help="Target <model>/<session>.")
    ],
    polygon: Annotated[str, typer.Option("--polygon")],
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Highlight Model geometry inside a snapshot-space polygon."""
    try:
        result = commands.lasso_preview(session, interaction.parse_polygon(polygon))
        if as_json:
            print(json.dumps(result))
        else:
            console.print_json(data=result)
    except Exception as exc:
        if as_json:
            _json_abort(exc)
        _abort(exc)


@lasso_app.command("apply")
def lasso_apply(
    session: Annotated[
        str, typer.Option("--session", help="Target <model>/<session>.")
    ],
    prompt: Annotated[str, typer.Option("--prompt")],
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Record a model prompt with the active lasso selection."""
    try:
        item, session_name = _prompt_target(session)
        path = interaction.lasso_path(bless_root(), item.name, session_name)
        if not path.is_file():
            raise RuntimeError(f"no lasso preview for {session}")
        state = json.loads(path.read_text())
        record = graph.add_prompt(
            item,
            session_name,
            "model",
            prompt,
            selection={"objects": state["objects"], "faces": state["faces"]},
        )
        graph.build_graph(item)
        commands.lasso_discard(session)
        result = {"prompt_id": record.id, "text": record.text}
        if as_json:
            print(json.dumps(result))
        else:
            console.print_json(data=result)
    except Exception as exc:
        if as_json:
            _json_abort(exc)
        _abort(exc)


@lasso_app.command("discard")
def lasso_discard(
    session: Annotated[
        str, typer.Option("--session", help="Target <model>/<session>.")
    ],
) -> None:
    """Clear the lasso highlight and preview state."""
    try:
        commands.lasso_discard(session)
    except Exception as exc:
        _abort(exc)


@app.command()
def compare(
    model: str,
    camera: Annotated[str, typer.Option("--camera")],
    versions: Annotated[str | None, typer.Option("--versions")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Select two camera-matched snapshots for ghost comparison."""
    try:
        pair = None
        if versions:
            try:
                a, b = (int(part) for part in versions.split(",", 1))
                pair = (a, b)
            except ValueError as exc:
                raise ValueError("--versions must be <a>,<b>") from exc
        result = interaction.compare_sidecars(bless_root(), model, camera, pair)
        if as_json:
            print(json.dumps(result))
        else:
            console.print_json(data=result)
    except Exception as exc:
        if as_json:
            _json_abort(exc)
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


@graph_app.command("import")
def graph_import(
    model: Annotated[str | None, typer.Argument(help="Model folder name.")] = None,
    all_models: Annotated[
        bool, typer.Option("--all", help="Import every model.")
    ] = False,
) -> None:
    """Import new omp user prompts into committed log/prompts.jsonl records."""
    try:
        for item in _models(model, all_models):
            records = graph.import_transcripts(item)
            counts = {
                layer: sum(r.layer == layer for r in records)
                for layer in ("model", "scene")
            }
            console.print(
                f"{item.name}: {len(records)} prompts "
                f"({counts['model']} model, {counts['scene']} scene)"
            )
    except Exception as exc:
        _abort(exc)


@graph_app.command("build")
def graph_build(
    model: Annotated[str | None, typer.Argument(help="Model folder name.")] = None,
    all_models: Annotated[
        bool, typer.Option("--all", help="Build every model.")
    ] = False,
) -> None:
    """Derive and strictly validate models/<model>/graph.json."""
    try:
        for item in _models(model, all_models):
            built = graph.build_graph(item)
            prompts = [
                node for node in built.nodes if isinstance(node, graph.PromptNode)
            ]
            links = [node for node in built.nodes if isinstance(node, graph.LinkNode)]
            console.print(
                f"{item.name}: {len(prompts)} prompts, {len(links)} links, "
                f"{len(built.references)} references, {len(built.cameras)} cameras"
            )
    except Exception as exc:
        _abort(exc)


def _prompt_target(selector: str) -> tuple[models.Model, str]:
    try:
        model_name, session = selector.split("/", 1)
    except ValueError as exc:
        raise ValueError("--session must be <model>/<session>") from exc
    validate_session_name(session)
    return models.resolve(model_name, bless_root() / "models"), session


@prompt_app.command("add")
def prompt_add(
    session: Annotated[
        str, typer.Option("--session", help="Target <model>/<session>.")
    ],
    layer: Annotated[Literal["model", "scene"], typer.Option("--layer")],
    text: Annotated[str, typer.Option("--text")],
) -> None:
    """Record a new agent-tagged prompt before acting on it."""
    try:
        item, session_name = _prompt_target(session)
        prompt = graph.add_prompt(item, session_name, layer, text)
        graph.build_graph(item)
        print(prompt.id)
    except Exception as exc:
        _abort(exc)


@prompt_app.command("tag")
def prompt_tag(model: str, prompt_id: str, layer: Literal["model", "scene"]) -> None:
    """Correct a prompt layer; user provenance survives future imports."""
    try:
        item = models.resolve(model, bless_root() / "models")
        prompt = graph.tag_prompt(item, prompt_id, layer)
        graph.build_graph(item)
        console.print_json(data=prompt.model_dump(exclude_none=True))
    except Exception as exc:
        _abort(exc)


@prompt_app.command("split")
def prompt_split(
    model: str,
    prompt_id: str,
    model_text: Annotated[str, typer.Option("--model-text")],
    scene_text: Annotated[str, typer.Option("--scene-text")],
) -> None:
    """Split a mixed prompt into model and scene nodes."""
    try:
        item = models.resolve(model, bless_root() / "models")
        split = graph.split_prompt(item, prompt_id, model_text, scene_text)
        graph.build_graph(item)
        console.print_json(
            data=[record.model_dump(exclude_none=True) for record in split]
        )
    except Exception as exc:
        _abort(exc)


@prompt_app.command("edit")
def prompt_edit(
    model: str,
    prompt_id: str,
    text: Annotated[str, typer.Option("--text")],
) -> None:
    """Edit prompt text and mark the source as user-owned."""
    try:
        item = models.resolve(model, bless_root() / "models")
        prompt = graph.edit_prompt(item, prompt_id, text)
        graph.build_graph(item)
        console.print_json(data=prompt.model_dump(exclude_none=True))
    except Exception as exc:
        _abort(exc)


@prompt_app.command("pin")
def prompt_pin(model: str, scene_id: str, model_id: str) -> None:
    """Pin a scene prompt to a specific model prompt."""
    try:
        item = models.resolve(model, bless_root() / "models")
        prompt = graph.pin_prompt(item, scene_id, model_id)
        graph.build_graph(item)
        console.print_json(data=prompt.model_dump(exclude_none=True))
    except Exception as exc:
        _abort(exc)


@app.command("replay")
def replay_cmd(
    target: str,
    from_id: Annotated[
        str | None, typer.Option("--from", help="Edited model prompt id.")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Plan without Blender.")
    ] = False,
) -> None:
    """Replay later model nodes and re-snapshot following scene nodes."""
    try:
        item, session = _prompt_target(target)
        plan = graph.replay(item, session, from_id, dry_run)
        console.print_json(data=plan.model_dump())
    except Exception as exc:
        _abort(exc)


def main() -> None:
    app()
