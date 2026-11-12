"""Pure Phase 4 state, projection, pin, and snapshot helpers."""

import json
import math
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def atomic_json(path: Path, payload) -> Path:
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
    return path


def sidecar_path(png: Path) -> Path:
    return Path(f"{png}.json")


def write_sidecar(png: Path, payload: dict) -> Path:
    return atomic_json(sidecar_path(png), payload)


def read_sidecar(png: Path) -> dict:
    path = sidecar_path(png)
    if not path.is_file():
        raise FileNotFoundError(f"snapshot sidecar does not exist: {path}")
    return json.loads(path.read_text())


def list_sidecars(root: Path, model: str, session: str | None = None) -> list[dict]:
    base = root / ".bless" / "snapshots" / model
    pattern = f"{session}/*.png.json" if session else "*/*.png.json"
    records = [json.loads(path.read_text()) for path in base.glob(pattern)]
    return sorted(records, key=lambda item: (item["created_at"], item["path"]))


def latest_sidecar(root: Path, model: str, session: str | None = None) -> dict | None:
    records = list_sidecars(root, model, session)
    return records[-1] if records else None


def current_version(root: Path, model: str) -> int | None:
    path = root / "models" / model / "graph.json"
    if not path.is_file():
        return None
    graph = json.loads(path.read_text())
    versions = [
        node["version"]
        for node in graph.get("nodes", [])
        if node.get("kind") == "prompt"
        and node.get("layer") == "model"
        and node.get("status") == "applied"
        and isinstance(node.get("version"), int)
    ]
    return max(versions, default=None)


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)
    ]


def _matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[index] * vector[index] for index in range(4)) for row in matrix]


def _inverse(matrix: list[list[float]]) -> list[list[float]]:
    work = [
        list(map(float, row)) + [float(i == j) for j in range(4)]
        for i, row in enumerate(matrix)
    ]
    for column in range(4):
        pivot = max(range(column, 4), key=lambda row: abs(work[row][column]))
        if abs(work[pivot][column]) < 1e-12:
            raise ValueError("view-projection matrix is singular")
        work[column], work[pivot] = work[pivot], work[column]
        scale = work[column][column]
        work[column] = [value / scale for value in work[column]]
        for row in range(4):
            if row == column:
                continue
            factor = work[row][column]
            work[row] = [
                value - factor * other
                for value, other in zip(work[row], work[column], strict=True)
            ]
    return [row[4:] for row in work]


def project_point(sidecar: dict, point: list[float]) -> list[float] | None:
    clip = _matvec(
        _matmul(sidecar["projection_matrix"], sidecar["view_matrix"]),
        [*point, 1.0],
    )
    if clip[3] <= 1e-9:
        return None
    x, y, z = (clip[index] / clip[3] for index in range(3))
    if z < -1.0 or z > 1.0:
        return None
    u, v = (x + 1.0) / 2.0, (1.0 - y) / 2.0
    return [u, v] if 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0 else None


def unproject_ray(sidecar: dict, u: float, v: float) -> tuple[list[float], list[float]]:
    if not (math.isfinite(u) and math.isfinite(v) and 0 <= u <= 1 and 0 <= v <= 1):
        raise ValueError("uv coordinates must be finite values in [0,1]")
    inverse = _inverse(_matmul(sidecar["projection_matrix"], sidecar["view_matrix"]))
    x, y = 2.0 * u - 1.0, 1.0 - 2.0 * v
    points = []
    for z in (-1.0, 1.0):
        value = _matvec(inverse, [x, y, z, 1.0])
        points.append([value[index] / value[3] for index in range(3)])
    direction = [points[1][index] - points[0][index] for index in range(3)]
    length = math.sqrt(sum(value * value for value in direction))
    return points[0], [value / length for value in direction]


def point_in_polygon(
    point: tuple[float, float], polygon: list[tuple[float, float]]
) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < cross:
                inside = not inside
        previous = current
    return inside


def parse_polygon(value: str) -> list[tuple[float, float]]:
    try:
        polygon = []
        for pair in value.split():
            parts = list(map(float, pair.split(",")))
            if len(parts) != 2:
                raise ValueError
            polygon.append((parts[0], parts[1]))
    except (TypeError, ValueError) as exc:
        raise ValueError("polygon must be 'u1,v1 u2,v2 …'") from exc
    if len(polygon) < 3:
        raise ValueError("polygon needs at least three u,v points")
    if any(not (0 <= u <= 1 and 0 <= v <= 1) for u, v in polygon):
        raise ValueError("polygon coordinates must be in [0,1]")
    return polygon


def pins_path(root: Path, model: str) -> Path:
    return root / ".bless" / "pins" / f"{model}.json"


def load_pins(root: Path, model: str) -> list[dict]:
    path = pins_path(root, model)
    return json.loads(path.read_text()) if path.is_file() else []


def add_pin(
    root: Path,
    model: str,
    session: str,
    thread: str,
    anchor: list[float],
    note: str | None,
) -> dict:
    pins = load_pins(root, model)
    pin = {
        "id": f"pin-{uuid.uuid4().hex[:12]}",
        "model": model,
        "session": session,
        "thread": thread,
        "anchor": anchor,
        "note": note,
        "created_at": iso_now(),
    }
    pins.append(pin)
    atomic_json(pins_path(root, model), pins)
    return pin


def remove_pin(root: Path, model: str, pin_id: str) -> None:
    pins = load_pins(root, model)
    kept = [pin for pin in pins if pin["id"] != pin_id]
    if len(kept) == len(pins):
        raise LookupError(f"no pin {pin_id!r}")
    atomic_json(pins_path(root, model), kept)


def pins_with_uv(root: Path, model: str, png: Path | None = None) -> list[dict]:
    sidecar = read_sidecar(png.resolve()) if png else None
    return [
        {**pin, "uv": project_point(sidecar, pin["anchor"]) if sidecar else None}
        for pin in load_pins(root, model)
    ]


def camera_records(root: Path, model: str) -> list[dict]:
    directory = root / ".bless" / "cameras" / model
    return (
        [
            {"thread": path.stem, **json.loads(path.read_text())}
            for path in sorted(directory.glob("*.json"))
        ]
        if directory.is_dir()
        else []
    )


def compare_sidecars(
    root: Path, model: str, camera: str, versions: tuple[int, int] | None = None
) -> dict:
    records = [
        item
        for item in list_sidecars(root, model)
        if item.get("camera") == camera and isinstance(item.get("version"), int)
    ]
    by_version = {
        version: max(
            (item for item in records if item["version"] == version),
            key=lambda item: item["created_at"],
        )
        for version in {item["version"] for item in records}
    }
    available = sorted(by_version)
    chosen = versions or (tuple(available[-2:]) if len(available) >= 2 else None)
    if (
        chosen is None
        or len(chosen) != 2
        or any(version not in by_version for version in chosen)
    ):
        raise ValueError(f"two snapshots are required; available versions: {available}")
    return {"camera": camera, "a": by_version[chosen[0]], "b": by_version[chosen[1]]}


def lasso_path(root: Path, model: str, session: str) -> Path:
    return root / ".bless" / "lasso" / model / f"{session}.json"
