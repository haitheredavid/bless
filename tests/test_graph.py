import json
from pathlib import Path

from blend.graph import (
    Graph,
    PromptRecord,
    build_graph,
    import_transcripts,
    pin_prompt,
    plan_replay,
    read_prompts,
    split_prompt,
    tag_prompt,
    write_prompts,
)
from blend.model import Model


def make_model(tmp_path: Path) -> Model:
    path = tmp_path / "models" / "chair"
    (path / "log").mkdir(parents=True)
    (path / "sessions").mkdir()
    (path / "model.toml").write_text('name = "chair"\nstatus = "active"\n')
    (path / "params.toml").write_text("[base]\nDepth = 1.0\n")
    (path / "sessions" / "2026-11-11-design.md").write_text(
        "# Design\n\n## Outcome\nBuilt.\n\n## Next\nReview.\n"
    )
    return Model(path)


def write_fixture_transcript(home: Path) -> Path:
    path = home / ".omp" / "agent" / "sessions" / "-projects-bless" / "fixture.jsonl"
    path.parent.mkdir(parents=True)
    rows = [
        {"type": "session", "timestamp": "2026-11-11T10:00:00Z", "cwd": "/repo"},
        {
            "type": "message",
            "id": "m1",
            "timestamp": "2026-11-11T10:00:10Z",
            "message": {
                "role": "user",
                "attribution": "user",
                "content": [{"type": "text", "text": "Add a beveled seat"}],
            },
        },
        {
            "type": "message",
            "timestamp": "2026-11-11T10:00:50Z",
            "message": {"role": "assistant", "content": []},
        },
        {
            "type": "message",
            "id": "m2",
            "timestamp": "2026-11-11T10:01:00Z",
            "message": {
                "role": "user",
                "attribution": "user",
                "content": [{"type": "text", "text": "Then show it from the side"}],
            },
        },
        {
            "type": "message",
            "id": "m3",
            "timestamp": "2026-11-11T10:02:00Z",
            "message": {
                "role": "user",
                "attribution": "user",
                "content": [{"type": "text", "text": "Push the branch"}],
            },
        },
        {
            "type": "message",
            "timestamp": "2026-11-11T10:02:10Z",
            "message": {"role": "assistant", "content": []},
        },
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def write_steps(model: Model) -> None:
    steps = [
        {
            "n": 1,
            "slug": "seat",
            "ts": "2026-11-11T10:00:30Z",
            "intent": "seat",
            "session": "2026-11-11-design",
            "code": "001-seat.py",
            "objects": ["Seat"],
            "params": {"Depth": 2.0},
            "speckle_version": "speckle-1",
        },
        {
            "n": 2,
            "slug": "view",
            "ts": "2026-11-11T10:01:30Z",
            "intent": "view",
            "session": "2026-11-11-design",
            "code": None,
            "objects": [],
            "params": {},
            "speckle_version": None,
        },
    ]
    (model.log_dir / "steps.jsonl").write_text(
        "".join(json.dumps(step) + "\n" for step in steps)
    )
    (model.log_dir / "001-seat.py").write_text("print('seat')\n")


def test_transcript_step_join_and_tag_preservation(tmp_path: Path) -> None:
    model = make_model(tmp_path)
    write_steps(model)
    write_fixture_transcript(tmp_path)

    imported = import_transcripts(model, tmp_path)
    assert [(record.text, record.steps) for record in imported] == [
        ("Add a beveled seat", [1]),
        ("Then show it from the side", []),
    ]
    assert [record.layer for record in imported] == ["model", "scene"]

    tag_prompt(model, imported[0].id, "scene")
    again = import_transcripts(model, tmp_path)
    assert len(again) == 2
    corrected = next(record for record in again if record.id == imported[0].id)
    assert corrected.layer == "scene"
    assert corrected.provenance == "user"


def test_unowned_step_fallback_is_replaced_when_transcript_claims_it(
    tmp_path: Path,
) -> None:
    model = make_model(tmp_path)
    step = {
        "n": 1,
        "slug": "seat",
        "ts": "2026-11-11T10:00:30Z",
        "intent": "Build the seat",
        "session": "2026-11-11-design",
        "code": "001-seat.py",
        "objects": ["Seat"],
        "params": {},
        "speckle_version": None,
    }
    (model.log_dir / "steps.jsonl").write_text(json.dumps(step) + "\n")
    (model.log_dir / "001-seat.py").write_text("print('seat')\n")

    first = import_transcripts(model, tmp_path)
    assert [(record.origin, record.steps, record.text) for record in first] == [
        ("step-log", [1], "Build the seat")
    ]

    transcript = (
        tmp_path / ".omp" / "agent" / "sessions" / "-projects-bless" / "later.jsonl"
    )
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps(
            {
                "type": "message",
                "id": "later-user",
                "timestamp": "2026-11-11T10:00:00Z",
                "message": {
                    "role": "user",
                    "attribution": "user",
                    "content": [{"type": "text", "text": "Build a seat"}],
                },
            }
        )
        + "\n"
        + json.dumps(
            {
                "type": "message",
                "timestamp": "2026-11-11T10:01:00Z",
                "message": {"role": "assistant", "content": []},
            }
        )
        + "\n"
    )
    second = import_transcripts(model, tmp_path)
    assert len(second) == 1
    assert second[0].origin == "transcript"
    assert second[0].steps == [1]


def test_split_produces_model_and_scene_records(tmp_path: Path) -> None:
    model = make_model(tmp_path)
    source = PromptRecord(
        id="p1",
        ts="2026-11-11T10:00:00Z",
        session="2026-11-11-design",
        layer="model",
        text="Bevel it and show me",
        provenance="agent",
        origin="agent",
    )
    write_prompts(model, [source])

    model_part, scene_part = split_prompt(model, "p1", "Bevel it", "Show me")
    assert (model_part.layer, scene_part.layer) == ("model", "scene")
    assert scene_part.id == "p1-scene"
    assert all(record.provenance == "user" for record in read_prompts(model))


def test_build_versions_shape_snapshot_and_pin(tmp_path: Path) -> None:
    model = make_model(tmp_path)
    image = model.path / "render.png"
    image.write_bytes(b"png")
    records = [
        PromptRecord(
            id="p1",
            ts="2026-11-11T10:00:00Z",
            session="2026-11-11-design",
            layer="model",
            text="Seat",
            steps=[1],
            status="applied",
            provenance="agent",
            origin="agent",
            snapshot="models/chair/render.png",
        ),
        PromptRecord(
            id="p2",
            ts="2026-11-11T10:01:00Z",
            session="2026-11-11-design",
            layer="scene",
            text="Show it",
            status="applied",
            provenance="agent",
            origin="agent",
        ),
        PromptRecord(
            id="p3",
            ts="2026-11-11T10:02:00Z",
            session="2026-11-11-design",
            layer="model",
            text="Legs",
            status="applied",
            provenance="agent",
            origin="agent",
        ),
        PromptRecord(
            id="p4",
            ts="2026-11-11T10:03:00Z",
            session="2026-11-11-design",
            layer="scene",
            text="Render the latest",
            status="applied",
            provenance="agent",
            origin="agent",
        ),
    ]
    write_prompts(model, records)
    write_steps(model)
    pin_prompt(model, "p2", "p1")

    built = build_graph(model, tmp_path)
    prompts = [node for node in built.nodes if node.kind == "prompt"]
    assert [node.version for node in prompts if node.layer == "model"] == [1, 2]
    assert prompts[0].snapshot == "models/chair/render.png"
    assert [(ref.scene, ref.model, ref.mode) for ref in built.references] == [
        ("p2", "p1", "pinned"),
        ("p4", "p3", "follows"),
    ]
    payload = json.loads((model.path / "graph.json").read_text())
    assert set(payload) == {"model", "sessions", "nodes", "references", "cameras"}
    assert all(
        set(node)
        <= {
            "id",
            "kind",
            "layer",
            "text",
            "session",
            "version",
            "speckle_version",
            "size",
            "status",
            "current",
            "camera",
            "step",
            "snapshot",
            "from",
            "to",
            "provenance",
            "parent",
            "snapshot_inferred",
        }
        for node in payload["nodes"]
    )
    assert {node["kind"] for node in payload["nodes"]} == {"prompt", "link"}


def test_replay_plan_same_session_followers_and_pins() -> None:
    graph = Graph.model_validate(
        {
            "model": "chair",
            "sessions": [
                {"id": "s1", "status": "open"},
                {"id": "s2", "status": "open"},
            ],
            "nodes": [
                {
                    "id": "p1",
                    "kind": "prompt",
                    "layer": "model",
                    "text": "one",
                    "session": "s1",
                    "version": 1,
                    "status": "applied",
                },
                {
                    "id": "p2",
                    "kind": "prompt",
                    "layer": "model",
                    "text": "two",
                    "session": "s1",
                    "version": 2,
                    "status": "applied",
                },
                {
                    "id": "other",
                    "kind": "prompt",
                    "layer": "model",
                    "text": "branch",
                    "session": "s2",
                    "version": 3,
                    "status": "applied",
                },
                {
                    "id": "p3",
                    "kind": "prompt",
                    "layer": "model",
                    "text": "three",
                    "session": "s1",
                    "version": 4,
                    "status": "applied",
                },
                {
                    "id": "follow",
                    "kind": "prompt",
                    "layer": "scene",
                    "text": "show",
                    "session": "s1",
                    "status": "applied",
                },
                {
                    "id": "pin",
                    "kind": "prompt",
                    "layer": "scene",
                    "text": "fixed",
                    "session": "s1",
                    "status": "applied",
                },
            ],
            "references": [
                {
                    "id": "r1",
                    "scene": "follow",
                    "model": "p3",
                    "mode": "follows",
                    "text": "latest",
                },
                {
                    "id": "r2",
                    "scene": "pin",
                    "model": "p1",
                    "mode": "pinned",
                    "text": "fixed",
                },
            ],
            "cameras": {},
        }
    )
    plan = plan_replay(graph, "p1")
    assert plan.model_nodes == ["p2", "p3"]
    assert plan.scene_followers == ["follow"]
    assert plan.pinned_untouched == ["pin"]


def test_camera_conversion_uses_quaternion_distance(tmp_path: Path) -> None:
    model = make_model(tmp_path)
    camera_dir = tmp_path / ".bless" / "cameras" / "chair"
    camera_dir.mkdir(parents=True)
    (camera_dir / "thread-1.json").write_text(
        json.dumps(
            {
                "target": [1, 2, 3],
                "distance": 4,
                "rotation": [1, 0, 0, 0],
                "lens": 35,
                "locked": True,
                "selected": ["Seat"],
                "params": {"Depth": 2.0, "Vector": [1, 2, 3]},
            }
        )
    )
    write_prompts(
        model,
        [
            PromptRecord(
                id="scene",
                ts="2026-11-11T10:00:00Z",
                session="2026-11-11-design",
                layer="scene",
                text="Show it",
                status="applied",
                provenance="agent",
                origin="agent",
                camera="thread-1",
            )
        ],
    )
    built = build_graph(model, tmp_path)
    camera = built.cameras["thread-1"]
    assert camera.position == (1.0, 2.0, 7.0)
    assert camera.params == {"Depth": 2.0}
