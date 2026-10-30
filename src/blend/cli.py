"""`blend` command line."""

import json
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from blend import blender, bridge, gallery, grid, printpack, printresults
from blend import model as models
from blend import site as sites
from blend.config import ROOT, get_settings
from blend.steplog import StepLog

app = typer.Typer(no_args_is_help=True, help="Blender models, iterated in sessions.")
model_app = typer.Typer(no_args_is_help=True, help="Create, list and close models.")
session_app = typer.Typer(no_args_is_help=True, help="Per-sitting session notes.")
app.add_typer(model_app, name="model")
app.add_typer(session_app, name="session")
console = Console()

README = ROOT / "README.md"
TILES = ROOT / "docs" / "gallery"
UNITS = {
    "m": (1.0, "METERS"),
    "cm": (0.01, "CENTIMETERS"),
    "mm": (0.001, "MILLIMETERS"),
}

ModelArg = Annotated[
    str, typer.Argument(help="Model folder name or unique part of it.")
]


def _model(ref: str) -> models.Model:
    try:
        return models.resolve(ref)
    except LookupError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)


def _need_blend(s: models.Model) -> None:
    if not s.blend.exists():
        console.print(f"[red]{s.blend} does not exist[/red]")
        raise typer.Exit(1)


def _run(script: str, **kwargs) -> dict:
    try:
        return blender.run_script(script, **kwargs)
    except blender.BlenderError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)


def _studio() -> Path:
    path = get_settings().studio_blend
    if not path.exists():
        _run("build_studio.py", args=["--save", str(path)], factory_startup=True)
        console.print(f"[dim]studio -> {path.relative_to(ROOT)}[/dim]")
    return path


def _render_args(s: models.Model, framing: str | None, scene: str | None) -> list:
    try:
        opts = s.render_options()
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)
    framing = framing or opts["framing"]
    if framing not in models.FRAMINGS:
        console.print(
            f"[red]--framing must be one of {', '.join(models.FRAMINGS)}[/red]"
        )
        raise typer.Exit(1)
    scene = scene or opts["scene"]
    return [
        "--studio",
        str(_studio()),
        "--framing",
        framing,
        *(["--scene", scene] if scene else []),
    ]


def _update_gallery() -> None:
    all_models = models.list_all()
    for tile in gallery.write_tiles(all_models, TILES):
        console.print(f"[dim]tile -> {tile.relative_to(ROOT)}[/dim]")
    md = gallery.gallery_markdown(all_models, ROOT, TILES)
    try:
        if gallery.update_readme(README, md):
            console.print("[dim]README gallery updated[/dim]")
    except LookupError as e:
        console.print(f"[yellow]{escape(str(e))}[/yellow]")


# --- models -----------------------------------------------------------------


@model_app.command("new")
def model_new(
    name: str,
    unit: Annotated[str, typer.Option(help="Length unit: m, cm or mm.")] = "m",
    no_blend: Annotated[bool, typer.Option(help="Skip creating model.blend.")] = False,
) -> None:
    """Create models/<name>/ from the template."""
    if unit not in UNITS:
        console.print(f"[red]--unit must be one of {', '.join(UNITS)}[/red]")
        raise typer.Exit(1)
    try:
        s = models.create(name)
    except FileExistsError as e:
        console.print(f"[red]{escape(str(e))} already exists[/red]")
        raise typer.Exit(1)
    scale, length_unit = UNITS[unit]
    s.toml.write_text(
        s.toml.read_text()
        .replace("scale_length = 1.0", f"scale_length = {scale}", 1)
        .replace('length_unit = "METERS"', f'length_unit = "{length_unit}"', 1)
    )
    if not no_blend:
        try:
            blender.run_script(
                "setup_scene.py",
                args=[
                    "--save",
                    str(s.blend),
                    "--scale-length",
                    str(scale),
                    "--length-unit",
                    length_unit,
                ],
                factory_startup=True,
            )
        except blender.BlenderError as e:
            console.print(f"[yellow]couldn't create model.blend:[/yellow] {e}")
    console.print(f"[green]created[/green] {s.path}")


@model_app.command("ls")
def model_ls() -> None:
    """List models, how far along each is, and their latest session."""
    table = Table("model", "status", "steps", "last session", "workflows")
    for s in models.list_all():
        note = s.latest_session()
        table.add_row(
            s.name,
            s.status(),
            str(len(StepLog(s).entries())),
            note.stem if note else "-",
            ", ".join(s.workflows),
        )
    console.print(table)


@model_app.command("latest")
def model_latest() -> None:
    """Print the active model worked on most recently."""
    try:
        print(models.latest().name)
    except LookupError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)


@model_app.command("done")
def model_done(ref: ModelArg) -> None:
    """Mark a model done and refresh the README gallery."""
    s = _model(ref)
    s.set_field("status", "done")
    console.print(f"[green]done[/green] {s.name}")
    _update_gallery()


@app.command("open")
def open_cmd(ref: ModelArg) -> None:
    """Open the model's model.blend in the Blender GUI (MCP bridge auto-starts)."""
    s = _model(ref)
    _need_blend(s)
    blender.open_gui(s.blend)
    console.print(f"opened {s.blend}")


@app.command()
def repl(
    ref: Annotated[
        str | None, typer.Argument(help="Model expected in Blender (warns if not).")
    ] = None,
    open_: Annotated[
        bool,
        typer.Option("--open", help="Launch Blender on the model if none is running."),
    ] = False,
    port: Annotated[int, typer.Option(help="blender-mcp bridge port.")] = bridge.PORT,
) -> None:
    """Command prompt for the live Blender: `gn Frame Depth 40`, or any Python."""
    from blend import repl as repl_mod

    s = _model(ref) if ref else None
    if not bridge.listening(port):
        if not (open_ and s):
            console.print(
                f"[red]no Blender on port {port}: `just open <model>` first, "
                "or `blend repl <model> --open`[/red]"
            )
            raise typer.Exit(1)
        _need_blend(s)
        blender.open_gui(s.blend)
        console.print(f"[dim]opening {s.blend.name}...[/dim]")
        if not bridge.wait_listening(port):
            console.print("[red]Blender did not start its bridge in time[/red]")
            raise typer.Exit(1)
    repl_mod.run(bridge.Bridge(port=port), expect=s)


# --- sessions and steps -------------------------------------------------------


@session_app.command("new")
def session_new(
    ref: ModelArg,
    name: Annotated[str, typer.Argument(help="Short slug for this sitting.")],
    goal: Annotated[str, typer.Option(help="One-line goal for the session.")] = "",
) -> None:
    """Start a session note: models/<m>/sessions/YYYY-MM-DD-<name>.md."""
    s = _model(ref)
    note = s.new_session(name, goal)
    print(note.relative_to(ROOT))


@session_app.command("latest")
def session_latest(ref: ModelArg) -> None:
    """Print the model's latest session note path."""
    note = _model(ref).latest_session()
    if note is None:
        console.print("[red]no sessions yet[/red]")
        raise typer.Exit(1)
    print(note.relative_to(ROOT))


@app.command()
def step(
    ref: ModelArg,
    name: Annotated[
        str | None, typer.Argument(help="Step slug (omit with --speckle-version).")
    ] = None,
    intent: Annotated[str, typer.Option(help="Why, in one line.")] = "",
    code_file: Annotated[
        Path | None, typer.Option(help="File holding the code that ran.")
    ] = None,
    obj: Annotated[
        list[str] | None, typer.Option("--object", help="Object touched (repeat).")
    ] = None,
    param: Annotated[
        list[str] | None, typer.Option(help="Param changed, as NAME=VALUE (repeat).")
    ] = None,
    speckle_version: Annotated[
        str | None,
        typer.Option(help="Speckle version id; alone, attaches to the latest step."),
    ] = None,
) -> None:
    """Log an iteration step to models/<m>/log/ (code kept verbatim)."""
    log = StepLog(_model(ref))
    if name is None:
        if not speckle_version:
            console.print("[red]give a step name, or --speckle-version alone[/red]")
            raise typer.Exit(1)
        try:
            st = log.set_speckle_version(speckle_version)
        except LookupError as e:
            console.print(f"[red]{escape(str(e))}[/red]")
            raise typer.Exit(1)
        console.print(f"step {st.n} {st.slug} -> speckle {speckle_version}")
        return
    params = {}
    for kv in param or []:
        key, sep, value = kv.partition("=")
        if not sep:
            console.print(f"[red]--param must be NAME=VALUE, not {kv!r}[/red]")
            raise typer.Exit(1)
        params[key.strip()] = _parse_value(value.strip())
    st = log.append(
        name,
        intent=intent,
        code=code_file.read_text() if code_file else None,
        suffix=code_file.suffix if code_file and code_file.suffix else ".py",
        objects=obj,
        params=params,
        speckle_version=speckle_version,
    )
    console.print(
        f"[green]step {st.n}[/green] {st.slug}" + (f" -> {st.code}" if st.code else "")
    )


def _parse_value(text: str):
    """--param values: numbers and booleans as such, everything else a string."""
    try:
        return tomllib.loads(f"v = {text}")["v"]
    except tomllib.TOMLDecodeError:
        return text


@app.command()
def history(
    ref: ModelArg,
    last: Annotated[int, typer.Option(help="Only the last N steps (0 = all).")] = 0,
) -> None:
    """The model's step timeline across sessions."""
    s = _model(ref)
    steps = StepLog(s).last(last)
    if not steps:
        console.print("[yellow]no steps logged yet[/yellow]")
        return
    table = Table("#", "when", "session", "step", "intent", "params", "speckle")
    for st in steps:
        table.add_row(
            str(st.n),
            st.ts[:16].replace("T", " "),
            st.session or "-",
            st.slug,
            st.intent,
            ", ".join(f"{k}={v}" for k, v in st.params.items()) or "-",
            st.speckle_version or "-",
        )
    console.print(table)


# --- outputs ----------------------------------------------------------------


def _flag(o: dict) -> list[str]:
    issues = []
    for key, label in (
        ("non_manifold_edges", "non-manifold"),
        ("loose_verts", "loose verts"),
        ("loose_edges", "loose edges"),
        ("degenerate_faces", "degenerate"),
        ("flipped_edges", "flipped normals"),
    ):
        if o[key]:
            issues.append(f"{o[key]} {label}")
    if o["negative_scale"]:
        issues.append("negative scale")
    return issues


@app.command()
def build(
    ref: ModelArg,
    variant: Annotated[
        str,
        typer.Option(help="params.toml variant applied over [base] (e.g. preview)."),
    ] = "base",
    allow_fail: Annotated[
        bool,
        typer.Option(help="Save model.blend even if checks.py fails (to inspect it)."),
    ] = False,
) -> None:
    """Rebuild the model headless from builders/ (build_all.py) and save model.blend.

    No MCP timeout. Fails on builder errors, GN inputs without a params key, and the
    model's builders/checks.py; model.blend is only saved when the build passes (or the
    checks fail and --allow-fail is set)."""
    s = _model(ref)
    _need_blend(s)
    if bridge.listening():
        console.print(
            "[yellow]a Blender is running: if it has this model open, save it first and "
            "revert it (File > Revert) after the build, or the two copies diverge[/yellow]"
        )
    args = ["--variant", variant] + (["--allow-fail"] if allow_fail else [])
    res = _run("build_model.py", blend=s.blend, args=args)
    rep = res.get("report") or {}
    for line in res.get(
        "log", []
    ):  # builder notes; skip build_all's own progress lines
        if line and not line.startswith(("build_all:", "build_all ok", "checks:")):
            console.print(f"[dim]{escape(line)}[/dim]")
    for w in rep.get("warns", []):
        console.print(f"[yellow]warn[/yellow] {escape(w)}")
    for f in rep.get("fails", []):
        console.print(f"[red]fail[/red] {escape(f)}")
    if rep.get("report"):
        console.print_json(json.dumps(rep["report"]))
    if not res["ok"]:
        console.print(
            f"[red]build failed ({res['seconds']} s)[/red]\n{escape(res['error'])}"
        )
        raise typer.Exit(1)
    console.print(
        f"[green]built[/green] {s.name} ({res['variant']}) in {res['seconds']} s"
    )


@app.command()
def check(
    ref: ModelArg,
    strict: Annotated[
        bool, typer.Option(help="Also fail on non-manifold / unapplied transforms.")
    ] = False,
    collection: Annotated[
        str, typer.Option(help="Collection to check (e.g. Print).")
    ] = "Model",
) -> None:
    """Mesh health of the Model collection: topology, normals, transforms, size."""
    s = _model(ref)
    _need_blend(s)
    res = _run("check_mesh.py", blend=s.blend, args=["--collection", collection])
    if not res["objects"]:
        console.print(f"[yellow]no visible mesh objects in {collection}[/yellow]")
        raise typer.Exit(1)
    table = Table(
        "object", "size", "faces", "tris", "ngons", "issues", "transforms",
        title=f"{s.name} {collection} (unit scale {res['unit_scale']:g})",
    )  # fmt: skip
    failed = False
    for o in res["objects"]:
        issues = _flag(o)
        if not strict:  # open surfaces are often intentional (planes, cloth, shells)
            issues = [i for i in issues if "non-manifold" not in i]
        failed |= bool(issues)
        tf = [
            n for n, k in (("scale", "unapplied_scale"), ("rot", "unapplied_rotation"))
            if o[k]
        ]  # fmt: skip
        failed |= strict and bool(tf)
        table.add_row(
            o["name"],
            " x ".join(f"{v:.3g}" for v in o["size"]),
            str(o["faces"]),
            str(o["tris"]),
            str(o["ngons"]),
            f"[red]{', '.join(_flag(o))}[/red]" if _flag(o) else "-",
            f"[yellow]{', '.join(tf)}[/yellow]" if tf else "-",
        )
    console.print(table)
    if failed:
        raise typer.Exit(1)


@app.command()
def export(
    ref: ModelArg,
    formats: Annotated[
        str | None,
        typer.Option(
            help="Comma-separated glb,fbx,obj,stl,3mf (default: [export] formats)."
        ),
    ] = None,
    split: Annotated[
        bool | None, typer.Option(help="One file per Model object.")
    ] = None,
    collection: Annotated[
        str | None,
        typer.Option(
            help="Collection to export (default: [export] collection, Model)."
        ),
    ] = None,
    web: Annotated[
        bool,
        typer.Option(
            help="Write web/model.glb (Model) and web/parts.glb ([site] parts) for "
            "the Pages viewer instead."
        ),
    ] = False,
) -> None:
    """Export the Model collection (or [export] collection, e.g. Print) to exports/."""
    s = _model(ref)
    _need_blend(s)
    if web:
        _export_web(s)
        return
    try:
        fmts = formats.split(",") if formats else s.export_formats()
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)
    if bad := [f for f in fmts if f not in models.EXPORT_FORMATS]:
        console.print(f"[red]unknown formats: {', '.join(bad)}[/red]")
        raise typer.Exit(1)
    if split is None:
        split = bool(s.config.get("export", {}).get("split", False))
    args = ["--outdir", str(s.exports), "--name", s.name, "--formats", ",".join(fmts)]
    args += ["--collection", collection or s.export_collection()]
    res = _run("export.py", blend=s.blend, args=args + (["--split"] if split else []))
    for path in res["written"]:
        console.print(f"[green]wrote[/green] {Path(path).relative_to(s.path)}")
    if not res["written"]:
        console.print("[yellow]nothing in Model to export[/yellow]")
        raise typer.Exit(1)


def _export_web(s: models.Model) -> None:
    parts = s.site_options()["parts"]
    for name, collection in (("model", "Model"), ("parts", parts)):
        if not collection:
            continue
        args = ["--outdir", str(s.web), "--name", name, "--formats", "glb"]
        res = _run("export.py", blend=s.blend, args=args + ["--collection", collection])
        for path in res["written"]:
            console.print(f"[green]wrote[/green] {Path(path).relative_to(s.path)}")
        if not res["written"]:
            if name == "model":
                console.print("[yellow]nothing in Model to export[/yellow]")
                raise typer.Exit(1)
            (s.web / "parts.glb").unlink(missing_ok=True)
            console.print(f"[dim]no {collection} collection: no parts.glb[/dim]")


@app.command()
def site(
    public: Annotated[
        Path, typer.Option(help="Where the site's static data goes.")
    ] = ROOT / "site" / "public",
) -> None:
    """Gather models with a web export (`blend export <m> --web`) into the Pages
    site: models.json plus each model's GLBs and render."""
    written = sites.build(models.list_all(), public)
    for path in written:
        console.print(f"[dim]{path.relative_to(public)}[/dim]")
    console.print(f"[green]{len(written) - 1} files, models.json[/green] -> {public}")


@app.command()
def render(
    ref: ModelArg,
    framing: Annotated[
        str | None,
        typer.Option(help="fit or wide (default: [render] framing, else fit)."),
    ] = None,
    scene: Annotated[
        str | None,
        typer.Option(help="Scene to render (default: [render] scene, else saved)."),
    ] = None,
) -> None:
    """Studio render of the Model collection to render.png; refreshes the gallery."""
    s = _model(ref)
    _need_blend(s)
    args = _render_args(s, framing, scene)
    res = _run("render_studio.py", blend=s.blend, args=[*args, "--out", str(s.render)])
    console.print(
        f"[green]rendered[/green] {s.render.relative_to(ROOT)} "
        f"({res['objects']} objects, {res['framing']}, {res['engine']})"
    )
    _update_gallery()


@app.command()
def views(
    ref: ModelArg,
    only: Annotated[
        list[str] | None, typer.Option(help="Render just these view names.")
    ] = None,
) -> None:
    """Render the model's [[views]] studio shots to out/views/<name>.png."""
    s = _model(ref)
    _need_blend(s)
    try:
        shots = s.views()
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)
    if only:
        if missing := set(only) - {v["name"] for v in shots}:
            console.print(f"[red]no such view(s): {', '.join(sorted(missing))}[/red]")
            raise typer.Exit(1)
        shots = [v for v in shots if v["name"] in only]
    if not shots:
        console.print("[yellow]no [[views]] in model.toml[/yellow]")
        raise typer.Exit(1)
    out_dir = s.out / "views"
    for v in shots:
        args = _render_args(s, v["framing"], None)
        args += ["--azimuth", str(v["azimuth"]), "--elevation", str(v["elevation"])]
        args += ["--size", str(v["size"]), "--zoom", str(v["zoom"])]
        args += ["--upright"] if v["upright"] else []
        args += [a for c in v["include"] for a in ("--include", c)]
        args += ["--target", *map(str, v["target"])] if v["target"] else []
        out = out_dir / f"{v['name']}.png"
        _run("render_studio.py", blend=s.blend, args=[*args, "--out", str(out)])
        console.print(f"[green]rendered[/green] {out.relative_to(ROOT)}")


@app.command()
def turntable(
    ref: ModelArg,
    frames: Annotated[int | None, typer.Option(help="Default: [turntable].")] = None,
    fps: Annotated[int | None, typer.Option(help="Default: [turntable].")] = None,
    framing: Annotated[str | None, typer.Option(help="fit or wide.")] = None,
    size: Annotated[int, typer.Option(help="Frame size in px.")] = 720,
) -> None:
    """360° studio turntable -> out/<model>-turntable.mp4 + .gif (needs ffmpeg)."""
    s = _model(ref)
    _need_blend(s)
    _ffmpeg()
    opts = s.turntable_options()
    frames, fps = frames or opts["frames"], fps or opts["fps"]
    frames_dir = s.out / "turntable"
    shutil.rmtree(frames_dir, ignore_errors=True)
    args = _render_args(s, framing, None)
    args += ["--out", str(frames_dir), "--frames", str(frames), "--fps", str(fps)]
    _run("render_studio.py", blend=s.blend, args=[*args, "--size", str(size)])
    mp4 = s.out / f"{s.name}-turntable.mp4"
    _encode(frames_dir, mp4, fps, start=1)
    console.print(
        f"[green]wrote[/green] {mp4.relative_to(ROOT)}, {mp4.with_suffix('.gif').name} "
        f"({frames} frames)"
    )


def _ffmpeg() -> str:
    ffmpeg = get_settings().ffmpeg_bin
    if not shutil.which(ffmpeg):
        console.print(f"[red]{ffmpeg} not found (brew install ffmpeg)[/red]")
        raise typer.Exit(1)
    return ffmpeg


def _encode(frames_dir: Path, mp4: Path, fps: int, start: int) -> None:
    """frames_dir/f%04d.png (numbered from start) -> mp4 + a looping gif beside it."""
    ffmpeg = _ffmpeg()
    pattern = str(frames_dir / "f%04d.png")
    for cmd in (
        [ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps),
         "-start_number", str(start), "-i", pattern,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(mp4)],
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(mp4), "-vf",
         "fps=15,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse",
         "-loop", "0", str(mp4.with_suffix(".gif"))],
    ):  # fmt: skip
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode:
            console.print(f"[red]ffmpeg failed:[/red] {escape(proc.stderr.strip())}")
            raise typer.Exit(1)


@app.command()
def animate(
    ref: ModelArg,
    start: Annotated[
        int | None, typer.Option(help="Default: the scene's start.")
    ] = None,
    end: Annotated[int | None, typer.Option(help="Default: the scene's end.")] = None,
    fps: Annotated[int, typer.Option(help="Frames per second.")] = 24,
    view: Annotated[str | None, typer.Option(help="Use this [[views]] angle.")] = None,
    size: Annotated[int, typer.Option(help="Frame size in px.")] = 720,
    name: Annotated[str, typer.Option(help="Output name in out/.")] = "animation",
    scene: Annotated[
        str | None, typer.Option(help="Scene to animate (e.g. Assembly).")
    ] = None,
    collection: Annotated[
        str | None, typer.Option(help="Collection to render (default Model).")
    ] = None,
    ortho: Annotated[bool, typer.Option(help="Orthographic camera.")] = False,
    isometric: Annotated[
        bool,
        typer.Option(help="Ortho camera at the isometric angle (az 45, el 35.264)."),
    ] = False,
    azimuth: Annotated[float | None, typer.Option(help="Camera azimuth (deg).")] = None,
    elevation: Annotated[
        float | None, typer.Option(help="Camera elevation (deg).")
    ] = None,
) -> None:
    """Render the scene's own animation (keyed params, exploded views) in the studio
    -> out/<name>.mp4 + .gif. Key it with kit.anim, save, then run this."""
    s = _model(ref)
    _need_blend(s)
    _ffmpeg()
    if start is None or end is None:
        rng = _run("scene_info.py", blend=s.blend, args=["--scene", scene or ""])
        start = rng["frame_start"] if start is None else start
        end = rng["frame_end"] if end is None else end
    if end <= start:
        console.print(f"[red]nothing to animate: frames {start}..{end}[/red]")
        raise typer.Exit(1)
    try:
        shots = {v["name"]: v for v in s.views()}
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)
    if view and view not in shots:
        console.print(f"[red]no [[views]] named {view!r}[/red]")
        raise typer.Exit(1)
    v = shots.get(view) if view else None
    args = _render_args(s, v["framing"] if v else None, scene)
    if isometric:
        azimuth, elevation, ortho = 45.0 if azimuth is None else azimuth, 35.264, True
    if v:
        azimuth = v["azimuth"] if azimuth is None else azimuth
        elevation = v["elevation"] if elevation is None else elevation
        args += ["--upright"] if v["upright"] else []
        args += [a for c in v["include"] for a in ("--include", c)]
    if azimuth is not None:
        args += ["--azimuth", str(azimuth)]
    if elevation is not None:
        args += ["--elevation", str(elevation)]
    args += ["--collection", collection] if collection else []
    args += ["--ortho"] if ortho else []
    frames_dir = s.out / name
    shutil.rmtree(frames_dir, ignore_errors=True)
    args += ["--animate", str(start), str(end), "--fps", str(fps), "--size", str(size)]
    _run("render_studio.py", blend=s.blend, args=[*args, "--out", str(frames_dir)])
    mp4 = s.out / f"{name}.mp4"
    _encode(frames_dir, mp4, fps, start=start)
    console.print(
        f"[green]wrote[/green] {mp4.relative_to(ROOT)}, {mp4.with_suffix('.gif').name} "
        f"(frames {start}-{end})"
    )


@app.command()
def variants(
    ref: ModelArg,
    only: Annotated[
        list[str] | None, typer.Option(help="Render just these variants.")
    ] = None,
    view: Annotated[
        str | None,
        typer.Option(help="Use this [[views]] shot (default: studio angle)."),
    ] = None,
    columns: Annotated[int, typer.Option(help="Grid columns.")] = 3,
    size: Annotated[int, typer.Option(help="Cell size in px.")] = 600,
) -> None:
    """Render every params.toml variant with the same shot -> out/variants.png grid."""
    s = _model(ref)
    _need_blend(s)
    try:
        sets = s.variants()
        shots = {v["name"]: v for v in s.views()}
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)
    if only:
        if missing := set(only) - set(sets):
            console.print(
                f"[red]no such variant(s): {', '.join(sorted(missing))}[/red]"
            )
            raise typer.Exit(1)
        sets = {k: v for k, v in sets.items() if k in only}
    if view and view not in shots:
        console.print(f"[red]no [[views]] named {view!r}[/red]")
        raise typer.Exit(1)
    v = shots.get(view) if view else None
    args = _render_args(s, v["framing"] if v else None, None)
    if v:
        args += ["--azimuth", str(v["azimuth"]), "--elevation", str(v["elevation"])]
        args += ["--zoom", str(v["zoom"])] + (["--upright"] if v["upright"] else [])
        args += [a for c in v["include"] for a in ("--include", c)]
        args += ["--target", *map(str, v["target"])] if v["target"] else []
    cells = []
    for name, params in sets.items():
        out = s.out / "variants" / f"{name}.png"
        res = _run(
            "render_studio.py",
            blend=s.blend,
            args=[*args, "--size", str(size), "--params", json.dumps(params),
                  "--out", str(out)],
        )  # fmt: skip
        if res.get("unused_params"):
            console.print(
                f"[yellow]{name}: no GN input for {', '.join(res['unused_params'])}[/yellow]"
            )
        console.print(f"[green]rendered[/green] {out.relative_to(ROOT)}")
        cells.append((name, out))
    sheet = grid.compose(cells, s.out / "variants.png", columns)
    console.print(f"[green]wrote[/green] {sheet.relative_to(ROOT)}")


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


@app.command("print-pack")
def print_pack(
    ref: ModelArg,
    collection: Annotated[
        str,
        typer.Option(
            help="Pack another collection (e.g. a test coupon) into print/<name>/, "
            "with [print.<name>] overriding [print]."
        ),
    ] = "",
) -> None:
    """Bake [print] collection parts into models/<m>/print/ for a printing agent:
    parts.blend (mm, on the bed), stl/, manifest.json, README.md."""
    s = _model(ref)
    _need_blend(s)
    cfg = s.print_options(collection)
    try:
        printpack.validate(cfg)
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)
    pack = collection.lower() if collection else "print"
    out = s.path / "print"
    if collection:
        out = out / pack
    args = ["--outdir", str(out), *printpack.blender_args(cfg)]
    res = _run("print_pack.py", blend=s.blend, args=args)
    source = {"commit": _git_commit(), "blend": str(s.blend.relative_to(ROOT))}
    intent = cfg.get("intent") or s.config.get("intent", "")
    m = printpack.manifest(
        s.name, res, cfg, ROOT, pack=pack, intent=intent, source=source
    )
    printpack.write(out, m)
    table = Table("part", "size (mm)", "cm³", "watertight", "fits bed", "intent")
    bad = False
    for p in m["parts"]:
        ok = p["manifold"] and p["fits_bed"]
        bad |= not ok
        o = p["orientation"]
        intent_bits = [o["mode"]] + [
            f"{k} {v}"
            for k, v in (
                ("supports", (p.get("supports") or {}).get("policy")),
                ("fil", p["filament"]),
                ("colour", (p.get("colour") or {}).get("method")),
                ("joints", len(p.get("joints", [])) or None),
            )
            if v
        ]
        table.add_row(
            p["name"],
            " x ".join(f"{v:g}" for v in p["size"]),
            f"{p['volume_cm3']:g}",
            "yes" if p["manifold"] else "[red]NO[/red]",
            "yes" if p["fits_bed"] else "[red]NO[/red]",
            ", ".join(map(str, intent_bits)),
        )
    console.print(table)
    for w in printpack.lint(m, cfg):
        console.print(f"[yellow]{escape(w)}[/yellow]")
    console.print(
        f"{len(m['parts'])} parts, {m['total_volume_cm3']} cm³, "
        f"{len(m['plates_suggested'])} suggested plates -> {out.relative_to(ROOT)}/"
    )
    if bad:
        raise typer.Exit(1)


@app.command("print-results")
def print_results(
    ref: ModelArg,
    pack: Annotated[
        str,
        typer.Option(
            help="Pack folder under print/ (e.g. coupon); main pack if empty."
        ),
    ] = "",
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """What bambi logged for a print pack (results.json): runs, and recommendations
    with their status (pending / applied / declined)."""
    s = _model(ref)
    pack_dir = s.path / "print" / pack.lower() if pack else s.path / "print"
    shown = pack_dir.relative_to(ROOT) if pack_dir.is_relative_to(ROOT) else pack_dir
    if not (pack_dir / printresults.RESULTS).exists():
        console.print(
            f"[yellow]no {printresults.RESULTS} in {shown}[/yellow]"
            " (bambi writes it on check/slice/print)"
        )
        raise typer.Exit(1)
    collection = next(
        (
            k
            for k, v in s.config.get("print", {}).items()
            if isinstance(v, dict) and k.lower() == pack.lower()
        ),
        pack,
    )
    rep = printresults.report(pack_dir, s.print_options(collection if pack else ""))
    if as_json:
        print(json.dumps(rep, indent=2))
        return
    runs = Table("id", "kind", "when", "facts", title=str(shown))
    for r in rep["runs"]:
        runs.add_row(r["id"], r["kind"], (r["at"] or "")[:16], escape(r["facts"]))
    console.print(runs)
    if rep["recommendations"]:
        recs = Table("id", "status", "target", "value", "reason", "from")
        colour = {"pending": "yellow", "applied": "green", "declined": "dim"}
        for r in rep["recommendations"]:
            c = colour.get(r["status"], "cyan")
            value = str(r.get("value", ""))
            if r.get("alt"):
                value += f" (alt: {r['alt']})"
            recs.add_row(
                r["id"],
                f"[{c}]{r['status']}[/{c}]",
                escape(str(r.get("target", ""))),
                escape(value),
                escape(str(r.get("reason", ""))),
                str(r.get("from", "")),
            )
        console.print(recs)
    else:
        console.print("[dim]no recommendations[/dim]")
    for note in rep["stale"]:
        console.print(f"[yellow]stale:[/yellow] {escape(note)}")
    if rep["pending"]:
        console.print(
            f"{len(rep['pending'])} pending: apply or decline each, record its id in "
            "[print] feedback_applied / feedback_declined, then `blend print-pack`."
        )


@app.command("patterns-lib")
def patterns_lib() -> None:
    """Build lib/patterns into assets/patterns.blend (node groups marked as assets)."""
    path = get_settings().patterns_blend
    res = _run("build_patterns.py", args=["--save", str(path)], factory_startup=True)
    console.print(
        f"[green]built[/green] {path.relative_to(ROOT)}: {', '.join(res['groups'])}"
    )


@app.command("render-scene")
def render_scene(
    overwrite: Annotated[
        bool, typer.Option(help="Replace it, discarding hand edits.")
    ] = False,
) -> None:
    """Build the studio .blend `blend render` uses (cyclorama, lights, camera)."""
    path = get_settings().studio_blend
    if path.exists() and not overwrite:
        console.print(
            f"[yellow]{path.relative_to(ROOT)} exists[/yellow] (--overwrite to rebuild)"
        )
        raise typer.Exit(1)
    _run("build_studio.py", args=["--save", str(path)], factory_startup=True)
    console.print(f"[green]built[/green] {path.relative_to(ROOT)}")


@app.command("gallery")
def gallery_cmd() -> None:
    """Rewrite the gallery tiles and the README grid from every model's render.png."""
    _update_gallery()


# --- workflows --------------------------------------------------------------


@app.command()
def workflows() -> None:
    """List workflows/ docs and the models that use each."""
    wdir = get_settings().workflows_dir
    used: dict[str, list[str]] = {}
    for s in models.list_all():
        for w in s.workflows:
            used.setdefault(w, []).append(s.name)
    table = Table("workflow", "summary", "models")
    docs = sorted(
        p for p in wdir.glob("*.md") if not p.name.startswith(("_", "README"))
    )
    for doc in docs:
        summary = next(
            (ln.strip() for ln in doc.read_text().splitlines()[1:] if ln.strip()), ""
        )
        table.add_row(doc.stem, summary, ", ".join(used.pop(doc.stem, [])) or "-")
    for missing, names in sorted(used.items()):
        table.add_row(f"[red]{missing}[/red]", "[red]no doc[/red]", ", ".join(names))
    console.print(table)
