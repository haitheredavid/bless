import json
from pathlib import Path

import pytest

from blend import interaction

IDENTITY = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]


def sidecar(tmp_path: Path, version: int = 1, camera: str = "thread") -> dict:
    png = tmp_path / ".bless" / "snapshots" / "chair" / "s" / f"{version}.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    png.touch()
    payload = {
        "schema": 1,
        "model": "chair",
        "session": "s",
        "path": str(png),
        "width": 100,
        "height": 80,
        "view_matrix": IDENTITY,
        "projection_matrix": IDENTITY,
        "is_perspective": False,
        "camera": camera,
        "version": version,
        "created_at": f"2026-11-12T00:00:0{version}+00:00",
    }
    interaction.write_sidecar(png, payload)
    return payload


def test_projection_unprojection_and_polygon() -> None:
    payload = {"view_matrix": IDENTITY, "projection_matrix": IDENTITY}
    assert interaction.project_point(payload, [0.0, 0.0, 0.0]) == [0.5, 0.5]
    origin, direction = interaction.unproject_ray(payload, 0.5, 0.5)
    assert origin == [0.0, 0.0, -1.0]
    assert direction == [0.0, 0.0, 1.0]
    square = interaction.parse_polygon("0.2,0.2 0.8,0.2 0.8,0.8 0.2,0.8")
    assert interaction.point_in_polygon((0.5, 0.5), square)
    assert not interaction.point_in_polygon((0.1, 0.5), square)


def test_pin_storage_and_snapshot_projection(tmp_path: Path) -> None:
    payload = sidecar(tmp_path)
    pin = interaction.add_pin(
        tmp_path, "chair", "2026-11-12-design", "thread", [0, 0, 0], "seat"
    )
    listed = interaction.pins_with_uv(tmp_path, "chair", Path(payload["path"]))
    assert listed == [{**pin, "uv": [0.5, 0.5]}]
    interaction.remove_pin(tmp_path, "chair", pin["id"])
    assert interaction.load_pins(tmp_path, "chair") == []


def test_compare_selects_latest_two_or_explicit_versions(tmp_path: Path) -> None:
    first = sidecar(tmp_path, 1)
    second = sidecar(tmp_path, 2)
    result = interaction.compare_sidecars(tmp_path, "chair", "thread")
    assert result == {"camera": "thread", "a": first, "b": second}
    assert (
        interaction.compare_sidecars(tmp_path, "chair", "thread", (2, 1))["a"] == second
    )
    with pytest.raises(ValueError, match=r"available versions: \[1, 2\]"):
        interaction.compare_sidecars(tmp_path, "chair", "thread", (2, 3))


def test_sidecar_latest_version_and_camera_records(tmp_path: Path) -> None:
    sidecar(tmp_path, 1)
    latest = sidecar(tmp_path, 2)
    assert interaction.latest_sidecar(tmp_path, "chair") == latest
    graph = tmp_path / "models" / "chair" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "kind": "prompt",
                        "layer": "model",
                        "status": "applied",
                        "version": 7,
                    }
                ]
            }
        )
    )
    assert interaction.current_version(tmp_path, "chair") == 7
    cameras = tmp_path / ".bless" / "cameras" / "chair"
    cameras.mkdir(parents=True)
    (cameras / "topic.json").write_text('{"schema":1,"target":[0,0,0]}')
    assert interaction.camera_records(tmp_path, "chair") == [
        {"thread": "topic", "schema": 1, "target": [0, 0, 0]}
    ]
