"""Direct, token-free commands against a supervised Blender add-on socket."""

import json
import math
import os
import re
import tempfile
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from blend import interaction
from blend.bridge import Bridge
from blend.model import Model
from blend.sessions import SessionRecord, bless_root, list_records, write_record


@dataclass(frozen=True)
class Target:
    record: SessionRecord
    root: Path

    @property
    def model(self) -> Model:
        return Model(self.root / "models" / self.record.model)

    def bridge(self) -> Bridge:
        if self.record.port is None:
            raise RuntimeError(
                f"session {self.record.model}/{self.record.session} has no port"
            )
        return Bridge(port=self.record.port, host="127.0.0.1")


def resolve_target(selector: str | None = None, root: Path | None = None) -> Target:
    root = (root or bless_root()).resolve()
    selector = selector or os.environ.get("BLESS_SESSION")
    records = list_records(root)
    if selector:
        try:
            model, session = selector.split("/", 1)
        except ValueError as exc:
            raise ValueError("session target must be <model>/<session>") from exc
        matches = [r for r in records if r.model == model and r.session == session]
        if not matches:
            raise LookupError(f"no Bless session {selector}")
        if matches[0].status != "ready":
            raise RuntimeError(
                f"Bless session {selector} is {matches[0].status}, not ready"
            )
        return Target(matches[0], root)
    ready = [record for record in records if record.status == "ready"]
    if len(ready) == 1:
        return Target(ready[0], root)
    candidates = (
        ", ".join(f"{r.model}/{r.session} ({r.status})" for r in records) or "none"
    )
    raise RuntimeError(
        f"select a session with --session or BLESS_SESSION; candidates: {candidates}"
    )


def _execute_json(target: Target, code: str):
    client = target.bridge()
    try:
        output = client.execute(code)
    finally:
        client.close()
    lines = [line for line in output.splitlines() if line.startswith("BLESS_JSON:")]
    if not lines:
        raise RuntimeError(f"Blender command returned no result: {output.strip()}")
    return json.loads(lines[-1].partition(":")[2])


VIEWPORT = """\
area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
if area is None:
    raise RuntimeError('no 3D viewport found')
space = area.spaces.active
r3d = space.region_3d
"""


def _view_spec(
    target: Target, name: str
) -> tuple[float, float, float, list[float] | None]:
    presets = {
        "front": (0.0, 0.0, 1.0, None),
        "side": (90.0, 0.0, 1.0, None),
        "top": (0.0, 90.0, 1.0, None),
        "iso": (45.0, 35.264, 1.0, None),
    }
    if name in presets:
        return presets[name]
    for view in target.model.views():
        if view["name"] == name:
            return view["azimuth"], view["elevation"], view["zoom"], view["target"]
    raise ValueError(
        f"unknown view {name!r}; use front, side, top, iso, camera:<id>, or a [[views]] name"
    )


def view_set(name: str, selector: str | None = None, root: Path | None = None) -> dict:
    target = resolve_target(selector, root)
    if name.startswith("camera:"):
        return camera_restore(name.partition(":")[2], selector, root)
    azimuth, elevation, zoom, configured_target = _view_spec(target, name)
    code = (
        VIEWPORT
        + f"""
from mathutils import Vector
import json, math
coll = bpy.data.collections.get('Model')
corners = []
if coll:
    dg = bpy.context.evaluated_depsgraph_get()
    corners = [obj.matrix_world @ Vector(corner) for obj in coll.all_objects
               if hasattr(obj, 'bound_box') for corner in obj.evaluated_get(dg).bound_box]
target = Vector({configured_target!r}) if {configured_target is not None!r} else (
    sum(corners, Vector()) / len(corners) if corners else Vector((0, 0, 0)))
radius = max(((corner - target).length for corner in corners), default=1.0)
az, el = math.radians({azimuth!r}), math.radians({elevation!r})
direction = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
r3d.view_location = target
r3d.view_distance = max(radius * 2.5 / {zoom!r}, 0.001)
r3d.view_rotation = direction.to_track_quat('Z', 'Y')
print('BLESS_JSON:' + json.dumps({{'view': {name!r}}}))
"""
    )
    return _execute_json(target, code)


def display_set(
    mode: str, selector: str | None = None, root: Path | None = None
) -> dict:
    shading = {
        "wire": "WIREFRAME",
        "solid": "SOLID",
        "material": "MATERIAL",
        "render": "RENDERED",
    }
    if mode not in shading:
        raise ValueError(f"unknown display mode {mode!r}")
    target = resolve_target(selector, root)
    code = (
        VIEWPORT
        + f"""
import json
space.shading.type = {shading[mode]!r}
print('BLESS_JSON:' + json.dumps({{'display': {mode!r}}}))
"""
    )
    return _execute_json(target, code)


def _camera_path(target: Target, thread_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", thread_id):
        raise ValueError(
            "thread id may contain only letters, numbers, dot, underscore, and dash"
        )
    return (
        target.root / ".bless" / "cameras" / target.record.model / f"{thread_id}.json"
    )


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(payload, stream, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


@contextmanager
def _snapshot_lock(directory: Path):
    """Serialize sequence allocation across CLI processes without reserving a PNG."""
    import fcntl

    lock = directory / ".snapshot.lock"
    with lock.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def camera_save(
    thread_id: str, selector: str | None = None, root: Path | None = None
) -> dict:
    target = resolve_target(selector, root)
    path = _camera_path(target, thread_id)
    lib = target.root / "lib"
    code = (
        VIEWPORT
        + f"""
import json, sys
from mathutils import Vector
sys.path.insert(0, {str(lib)!r})
from kit import gn, params, scene
def plain(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return list(value)
    except TypeError:
        return str(value)
current = {{}}
for key in params.load():
    owner, _, input_name = key.rpartition('/')
    for obj in scene.model().all_objects:
        if owner and owner != obj.name:
            continue
        match = next((mod for mod in gn.gn_modifiers(obj) if gn.has_input(mod, input_name)), None)
        if match:
            current[key] = plain(gn.get_input(match, input_name))
            break
camera = {{
    'schema': 1,
    'position': list(r3d.view_matrix.inverted().translation),
    'target': list(r3d.view_location),
    'distance': r3d.view_distance,
    'rotation': list(r3d.view_rotation),
    'lens': space.lens,
    'locked': bool(space.lock_camera),
    'selected': [obj.name for obj in bpy.context.selected_objects],
    'params': current,
}}
print('BLESS_JSON:' + json.dumps(camera))
"""
    )
    camera = _execute_json(target, code)
    _atomic_json(path, camera)
    return {"camera": str(path.resolve())}


def camera_restore(
    thread_id: str, selector: str | None = None, root: Path | None = None
) -> dict:
    target = resolve_target(selector, root)
    path = _camera_path(target, thread_id)
    camera = json.loads(path.read_text())
    lib = target.root / "lib"
    code = (
        VIEWPORT
        + f"""
import json, sys
from mathutils import Quaternion, Vector
sys.path.insert(0, {str(lib)!r})
from kit import params
camera = {camera!r}
r3d.view_location = Vector(camera['target'])
r3d.view_distance = camera['distance']
r3d.view_rotation = Quaternion(camera['rotation'])
space.lens = camera['lens']
space.lock_camera = camera['locked']
bpy.ops.object.select_all(action='DESELECT')
for name in camera['selected']:
    if name in bpy.data.objects:
        bpy.data.objects[name].select_set(True)
applied = params.apply(camera['params'])
print('BLESS_JSON:' + json.dumps({{'camera': {thread_id!r}, 'params': len(applied['set'])}}))
"""
    )
    return _execute_json(target, code)


def snapshot(
    camera: str | None = None,
    selector: str | None = None,
    root: Path | None = None,
    prompt_id: str | None = None,
) -> Path:
    target = resolve_target(selector, root)
    if camera:
        camera_restore(camera.removeprefix("camera:"), selector, root)
    label = camera.removeprefix("camera:") if camera else "viewport"
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "viewport"
    directory = (
        target.root
        / ".bless"
        / "snapshots"
        / target.record.model
        / target.record.session
    )
    directory.mkdir(parents=True, exist_ok=True)
    with _snapshot_lock(directory):
        sequences = [
            int(prefix)
            for path in directory.glob("*-*.png")
            if (prefix := path.name.partition("-")[0]).isdigit()
        ]
        sequence = max(sequences, default=0) + 1
        path = directory / f"{sequence:04d}-{label}.png"
        client = target.bridge()
        try:
            result = client.send(
                "get_viewport_screenshot",
                max_size=1600,
                filepath=str(path),
                format="png",
            )
        finally:
            client.close()
    if not path.is_file():
        raise RuntimeError(f"Blender did not write snapshot: {result}")
    view = result.get("view") or _execute_json(
        target,
        VIEWPORT
        + """
import json
print('BLESS_JSON:' + json.dumps({
    'view_matrix': [list(row) for row in r3d.view_matrix],
    'window_matrix': [list(row) for row in r3d.window_matrix],
    'width': area.width,
    'height': area.height,
}))
""",
    )
    perspective = _execute_json(
        target,
        VIEWPORT
        + """
import json
print('BLESS_JSON:' + json.dumps({'is_perspective': bool(r3d.is_perspective)}))
""",
    )
    sidecar = {
        "schema": 1,
        "model": target.record.model,
        "session": target.record.session,
        "path": str(path.resolve()),
        "width": int(result.get("width", view["width"])),
        "height": int(result.get("height", view["height"])),
        "view_matrix": view["view_matrix"],
        "projection_matrix": view["window_matrix"],
        "is_perspective": perspective["is_perspective"],
        "camera": camera.removeprefix("camera:") if camera else None,
        "version": interaction.current_version(target.root, target.record.model),
        "prompt_id": prompt_id,
        "created_at": interaction.iso_now(),
    }
    interaction.write_sidecar(path.resolve(), sidecar)
    record = next(
        r
        for r in list_records(target.root)
        if r.model == target.record.model and r.session == target.record.session
    )
    record.last_snapshot = str(path.resolve())
    write_record(record, target.root)
    return path.resolve()


def camera_list(model: str, root: Path | None = None) -> list[dict]:
    return interaction.camera_records((root or bless_root()).resolve(), model)


def pin_add(
    selector: str,
    uv: tuple[float, float],
    thread: str,
    note: str | None = None,
    root: Path | None = None,
) -> dict:
    target = resolve_target(selector, root)
    sidecar = interaction.latest_sidecar(
        target.root, target.record.model, target.record.session
    )
    if sidecar is None:
        raise RuntimeError(f"no snapshot for {selector}")
    origin, direction = interaction.unproject_ray(sidecar, *uv)
    code = f"""
import json
from mathutils import Vector
depsgraph = bpy.context.evaluated_depsgraph_get()
hit, location, normal, face, obj, matrix = bpy.context.scene.ray_cast(
    depsgraph, Vector({origin!r}), Vector({direction!r}))
print('BLESS_JSON:' + json.dumps({{'hit': hit, 'location': list(location) if hit else None}}))
"""
    hit = _execute_json(target, code)
    if not hit["hit"]:
        raise RuntimeError(f"ray from {uv[0]},{uv[1]} missed the scene")
    camera_save(thread, selector, target.root)
    return interaction.add_pin(
        target.root,
        target.record.model,
        target.record.session,
        thread,
        hit["location"],
        note,
    )


def _lasso_clear(target: Target) -> None:
    _execute_json(
        target,
        """
import json
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
print('BLESS_JSON:' + json.dumps({'cleared': True}))
""",
    )


def lasso_preview(
    selector: str, polygon: list[tuple[float, float]], root: Path | None = None
) -> dict:
    target = resolve_target(selector, root)
    sidecar = interaction.latest_sidecar(
        target.root, target.record.model, target.record.session
    )
    if sidecar is None:
        raise RuntimeError(f"no snapshot for {selector}")
    code = f"""
import json
from mathutils import Matrix
view = Matrix({sidecar["view_matrix"]!r})
projection = Matrix({sidecar["projection_matrix"]!r})
polygon = {polygon!r}
def inside(point):
    x, y = point
    result = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            result = not result
        previous = current
    return result
def screen(point):
    clip = projection @ view @ point.to_4d()
    if clip.w <= 1e-9:
        return None
    return ((clip.x/clip.w+1)/2, (1-clip.y/clip.w)/2)
bpy.ops.object.select_all(action='DESELECT')
collection = bpy.data.collections.get('Model')
objects = []
faces = 0
depsgraph = bpy.context.evaluated_depsgraph_get()
for obj in collection.all_objects if collection else []:
    if obj.type != 'MESH':
        continue
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        projected = [screen(obj.matrix_world @ vertex.co) for vertex in mesh.vertices]
        selected_faces = sum(
            inside(screen(obj.matrix_world @ polygon.center))
            or any(projected[index] is not None and inside(projected[index]) for index in polygon.vertices)
            for polygon in mesh.polygons
            if screen(obj.matrix_world @ polygon.center) is not None
        )
        selected = selected_faces > 0 or any(point is not None and inside(point) for point in projected)
        if selected:
            obj.select_set(True)
            objects.append(obj.name)
            faces += selected_faces
    finally:
        evaluated.to_mesh_clear()
if objects:
    bpy.context.view_layer.objects.active = bpy.data.objects.get(objects[0])
print('BLESS_JSON:' + json.dumps({{'objects': objects, 'faces': faces}}))
"""
    selected = _execute_json(target, code)
    preview_path = snapshot(None, selector, target.root)
    state = {
        "lasso_id": f"lasso-{interaction.iso_now().replace(':', '').replace('+', '-')}",
        "model": target.record.model,
        "session": target.record.session,
        "polygon": polygon,
        "objects": selected["objects"],
        "faces": selected["faces"],
        "preview": str(preview_path),
    }
    interaction.atomic_json(
        interaction.lasso_path(target.root, target.record.model, target.record.session),
        state,
    )
    return {
        "lasso_id": state["lasso_id"],
        "objects": state["objects"],
        "faces": state["faces"],
        "preview": interaction.read_sidecar(preview_path),
    }


def lasso_discard(selector: str, root: Path | None = None) -> None:
    target = resolve_target(selector, root)
    _lasso_clear(target)
    interaction.lasso_path(
        target.root, target.record.model, target.record.session
    ).unlink(missing_ok=True)


def _coerce_value(raw: str, current):
    if isinstance(current, bool):
        if raw.lower() not in {"true", "false"}:
            raise ValueError("boolean parameter values must be true or false")
        return raw.lower() == "true"
    if isinstance(current, int) and not isinstance(current, bool):
        return int(raw)
    if isinstance(current, float):
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError("number parameter values must be finite")
        return value
    return raw


def param_set(
    name: str, raw_value: str, selector: str | None = None, root: Path | None = None
) -> dict:
    target = resolve_target(selector, root)
    with target.model.params_toml.open("rb") as stream:
        base = tomllib.load(stream).get("base", {})
    if name not in base:
        raise ValueError(f"unknown parameter {name!r}; known: {', '.join(base)}")
    value = _coerce_value(raw_value, base[name])
    lib = target.root / "lib"
    code = f"""
import json, sys
sys.path.insert(0, {str(lib)!r})
from kit import params
result = params.apply({{{name!r}: {value!r}}})
print('BLESS_JSON:' + json.dumps(result))
"""
    result = _execute_json(target, code)
    if result["unused"]:
        raise RuntimeError(f"no live Geometry Nodes input matches {name!r}")
    return result


def check(selector: str | None = None, root: Path | None = None) -> dict:
    target = resolve_target(selector, root)
    scripts = target.root / "blender_scripts"
    code = f"""
import json, sys
sys.path.insert(0, {str(scripts)!r})
from mesh_health import report
print('BLESS_JSON:' + json.dumps(report('Model')))
"""
    return _execute_json(target, code)
