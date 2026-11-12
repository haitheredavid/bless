"""Prompt source import and strict explorer graph derivation.

Heuristics are intentionally centralized here:
- prompts owning code/param steps are model-layer;
- otherwise scene vocabulary wins, then modeling vocabulary;
- operational chat with neither is excluded;
- size combines touched objects, changed params, and capped code bytes, then normalizes
  by the largest applied model prompt in that model;
- links use a leading connective phrase, falling back to ``next``.
"""

import hashlib
import itertools
import json
import os
import re
import tempfile
import warnings
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blend.model import Model
from blend.sessions import bless_root, list_records

SCENE_WORDS = re.compile(
    r"\b(camera|view|show|look|render|snapshot|lighting?|display|wireframe|solid|"
    r"material preview|turntable|frame(?:d|ing)?|angle|zoom|orbit)\b",
    re.IGNORECASE,
)
MODEL_WORDS = re.compile(
    r"\b(model|geometry|mesh|bevel|fillet|thicken|thin(?:ner)?|add|remove|make|"
    r"change|attach|join|cut|curve|surface|part|frame|head|leg|seat|joint|slot|"
    r"hole|clip|prong|rail|spline|key|dimension|width|height|depth|radius|"
    r"clearance|parameter|parametric|shape|outline|profile)\b",
    re.IGNORECASE,
)
OPERATIONAL_WORDS = re.compile(
    r"\b(commit|push|branch|pull request|merge|ci|test suite|print(?:er|ing)?|slice|"
    r"cloud|deploy|readme|documentation|status update)\b",
    re.IGNORECASE,
)
CONNECTIVE = re.compile(
    r"^\s*(under it|over it|beside it|then|now|also|next|or try|instead|"
    r"tie (?:the )?[^,.!?]{0,32} with|raise it|lower it|thinner|thicker)\b",
    re.IGNORECASE,
)
PIN_WORDS = re.compile(r"\b(?:version|step)\s+(\d+)\b", re.IGNORECASE)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class PromptRecord(BaseModel):
    """Committed source record; deliberately richer than graph.ts PromptNode."""

    model_config = ConfigDict(extra="forbid")

    id: str
    ts: str
    session: str
    layer: Literal["model", "scene"]
    text: str
    steps: list[int] = Field(default_factory=list)
    status: Literal["applied", "preview", "queued", "dropped"] = "applied"
    provenance: Literal["heuristic", "agent", "user", "step-log"]
    origin: Literal["transcript", "agent", "step-log"]
    import_key: str | None = None
    transcript: str | None = None
    message_id: str | None = None
    camera: str | None = None
    snapshot: str | None = None
    split_from: str | None = None
    pinned_model: str | None = None
    selection: dict | None = None


class PromptNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: Literal["prompt"] = "prompt"
    layer: Literal["model", "scene"]
    text: str
    session: str = Field(min_length=1)
    version: int | None = Field(default=None, gt=0)
    speckle_version: str | None = Field(default=None, min_length=1)
    size: float | None = Field(default=None, ge=0)
    status: Literal["applied", "preview", "queued", "dropped"]
    current: bool | None = None
    camera: str | None = Field(default=None, min_length=1)
    step: int | None = Field(default=None, ge=0)
    snapshot: str | None = Field(default=None, min_length=1)


class LinkNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: Literal["link"] = "link"
    text: str
    from_: str = Field(alias="from", min_length=1)
    to: str = Field(min_length=1)


class GraphSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    parent_node: str | None = Field(default=None, min_length=1)


class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    scene: str = Field(min_length=1)
    model: str = Field(min_length=1)
    mode: Literal["pinned", "follows"]
    text: str


Scalar = str | int | float | bool | None


class CameraRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: tuple[float, float, float]
    target: tuple[float, float, float]
    lens_mm: float = Field(gt=0)
    locked: bool
    selection: list[str]
    params: dict[str, Scalar]


class Graph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
    sessions: list[GraphSession]
    nodes: list[PromptNode | LinkNode]
    references: list[Reference]
    cameras: dict[str, CameraRecord]

    @model_validator(mode="after")
    def valid_endpoints(self):
        ids = {node.id for node in self.nodes}
        for node in self.nodes:
            if isinstance(node, LinkNode) and ({node.from_, node.to} - ids):
                raise ValueError(f"link {node.id} points to a missing node")
        for ref in self.references:
            if ref.scene not in ids:
                raise ValueError(f"reference {ref.id} has no scene node")
            if ref.mode == "pinned" and ref.model not in ids:
                raise ValueError(f"reference {ref.id} has no model node")
        return self


def prompts_path(model: Model) -> Path:
    return model.log_dir / "prompts.jsonl"


def graph_path(model: Model) -> Path:
    return model.path / "graph.json"


def read_prompts(model: Model) -> list[PromptRecord]:
    path = prompts_path(model)
    if not path.exists():
        return []
    return [
        PromptRecord.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def write_prompts(model: Model, records: list[PromptRecord]) -> Path:
    path = prompts_path(model)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(record.model_dump(exclude_none=True), separators=(",", ":")) + "\n"
        for record in sorted(records, key=lambda item: (parse_time(item.ts), item.id))
    )
    _atomic_text(path, text)
    return path


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def read_steps(model: Model) -> list[dict]:
    path = model.log_dir / "steps.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class TranscriptPrompt(BaseModel):
    path: Path
    message_id: str
    ts: str
    text: str
    next_ts: str | None = None


def transcript_files(home: Path | None = None) -> list[Path]:
    base = home or Path.home()
    return sorted(
        (base / ".omp" / "agent" / "sessions").glob("-projects-bless*/*.jsonl")
    )


def _content_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(block.get("text", "")).strip()
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
    ).strip()


def read_transcript(path: Path) -> list[TranscriptPrompt]:
    found = []
    last_event: datetime | None = None
    for line in path.read_text(errors="replace").splitlines():
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = raw.get("message", {})
        if event_time := raw.get("timestamp") or message.get("timestamp"):
            parsed_event = parse_time(event_time)
            last_event = max(last_event, parsed_event) if last_event else parsed_event
        if (
            raw.get("type") != "message"
            or message.get("role") != "user"
            or message.get("attribution") != "user"
        ):
            continue
        text = _content_text(message.get("content"))
        timestamp = raw.get("timestamp") or message.get("timestamp")
        if text and timestamp:
            found.append(
                TranscriptPrompt(
                    path=path,
                    message_id=str(
                        raw.get("id") or hashlib.sha1(line.encode()).hexdigest()
                    ),
                    ts=timestamp,
                    text=text,
                )
            )
    found.sort(key=lambda item: parse_time(item.ts))
    for current, following in itertools.pairwise(found):
        current.next_ts = following.ts
    if found and last_event:
        found[-1].next_ts = (last_event + timedelta(microseconds=1)).isoformat()
    return found


def _owns(prompt: TranscriptPrompt, timestamp: str) -> bool:
    value = parse_time(timestamp)
    return parse_time(prompt.ts) <= value and (
        prompt.next_ts is None or value < parse_time(prompt.next_ts)
    )


def _stable_id(model: str, import_key: str) -> str:
    digest = hashlib.sha1(f"{model}:{import_key}".encode()).hexdigest()[:12]
    return f"p-{digest}"


def _split_mixed(text: str, has_model: bool) -> tuple[str, str] | None:
    if not has_model or not SCENE_WORDS.search(text):
        return None
    match = re.search(
        r"\b(?:and|then)\s+(?=(?:show|render|display|frame|take|capture|switch|"
        r"use|move|orbit|zoom)\b)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    left, right = text[: match.start()].strip(" ,;"), text[match.end() :].strip(" ,;")
    return (left, right) if left and right else None


def _include_prompt(text: str, steps: list[dict]) -> bool:
    changes_model = any(step.get("code") or step.get("params") for step in steps)
    if (
        text.lstrip().startswith(("# Model:", "# Session:", "# Wrap:"))
        and not changes_model
    ):
        return False
    if changes_model or SCENE_WORDS.search(text) or MODEL_WORDS.search(text):
        return True
    return not OPERATIONAL_WORDS.search(text) and False


def _layer(text: str, steps: list[dict]) -> Literal["model", "scene"]:
    if any(step.get("code") or step.get("params") for step in steps):
        return "model"
    return "scene" if SCENE_WORDS.search(text) else "model"


def import_transcripts(model: Model, home: Path | None = None) -> list[PromptRecord]:
    """Import new transcript prompts, preserving every existing source record."""
    home_root = (home or Path.home()).resolve()
    steps = read_steps(model)
    transcripts = {path: read_transcript(path) for path in transcript_files(home)}
    model_phrases = {
        model.name.lower(),
        model.name.replace("-", " ").lower(),
        *{stem.lower() for stem in (path.stem for path in model.session_notes())},
    }
    explicit_paths = {
        path
        for path, prompts in transcripts.items()
        if any(
            any(phrase in prompt.text.lower() for phrase in model_phrases)
            for prompt in prompts
        )
    }
    assignments: dict[tuple[Path, str], list[dict]] = defaultdict(list)
    for step in steps:
        candidates = [
            prompt
            for path, prompts in transcripts.items()
            if not explicit_paths or path in explicit_paths
            for prompt in prompts
            if _owns(prompt, step["ts"])
        ]
        if candidates:
            owner = max(candidates, key=lambda item: parse_time(item.ts))
            assignments[(owner.path, owner.message_id)].append(step)

    note_stems = {path.stem for path in model.session_notes()}
    relevant = {
        path
        for path, prompts in transcripts.items()
        if any((path, prompt.message_id) in assignments for prompt in prompts)
        or path in explicit_paths
    }
    generated: list[PromptRecord] = []
    transcript_claimed_steps: set[int] = set()
    for path in relevant:
        prompts = transcripts[path]
        owned_sessions = {
            prompt.message_id: [
                step.get("session")
                for step in assignments.get((path, prompt.message_id), [])
                if step.get("session")
            ]
            for prompt in prompts
        }
        known = [session for values in owned_sessions.values() for session in values]
        default_session = Counter(known).most_common(1)[0][0] if known else None
        if default_session is None:
            raw = path.read_text(errors="ignore")
            default_session = next((stem for stem in note_stems if stem in raw), None)
        if default_session is None:
            continue
        anchored = [prompt for prompt in prompts if owned_sessions[prompt.message_id]]
        for prompt in prompts:
            owned = assignments.get((path, prompt.message_id), [])
            if not _include_prompt(prompt.text, owned):
                continue
            transcript_claimed_steps.update(int(step["n"]) for step in owned)
            sessions = owned_sessions[prompt.message_id]
            if sessions:
                session = Counter(sessions).most_common(1)[0][0]
            elif anchored:
                nearest = min(
                    anchored,
                    key=lambda item: abs(
                        (parse_time(item.ts) - parse_time(prompt.ts)).total_seconds()
                    ),
                )
                session = owned_sessions[nearest.message_id][0]
            else:
                session = default_session
            if not isinstance(session, str):
                continue
            has_model = any(
                step.get("code") or step.get("params") for step in owned
            ) or bool(MODEL_WORDS.search(prompt.text))
            split = _split_mixed(prompt.text, has_model)
            parts = (
                [("model", split[0]), ("scene", split[1])]
                if split
                else [(_layer(prompt.text, owned), prompt.text)]
            )
            base_key = f"{prompt.message_id}:{prompt.ts}"
            base_id = _stable_id(model.name, base_key)
            for layer, text in parts:
                import_key = f"{base_key}:{layer}" if split else base_key
                generated.append(
                    PromptRecord(
                        id=base_id
                        if layer == "model" or not split
                        else f"{base_id}-scene",
                        ts=prompt.ts,
                        session=session,
                        layer=layer,
                        text=text,
                        steps=[int(step["n"]) for step in owned]
                        if layer == "model"
                        else [],
                        status="applied" if owned or layer == "scene" else "queued",
                        provenance="heuristic",
                        origin="transcript",
                        import_key=import_key,
                        transcript=str(path.relative_to(home_root)),
                        message_id=prompt.message_id,
                        split_from=base_id if split else None,
                    )
                )

    deduplicated: dict[str, PromptRecord] = {}
    for record in generated:
        current = deduplicated.get(record.import_key or record.id)
        if current is None or len(record.steps) > len(current.steps):
            deduplicated[record.import_key or record.id] = record
    generated = list(deduplicated.values())
    claimed_steps = transcript_claimed_steps | {
        number
        for record in generated
        if record.origin == "transcript"
        for number in record.steps
    }
    for step in steps:
        number = int(step["n"])
        if number in claimed_steps or not step.get("session"):
            continue
        intent = str(step.get("intent") or step.get("slug") or f"Step {number}")
        generated.append(
            PromptRecord(
                id=f"step-{number}",
                ts=step["ts"],
                session=step["session"],
                layer=_layer(intent, [step]),
                text=intent,
                steps=[number],
                status="applied",
                provenance="step-log",
                origin="step-log",
                import_key=f"step:{number}",
            )
        )

    existing = []
    for record in read_prompts(model):
        superseded = record.origin == "step-log" and bool(
            set(record.steps) & claimed_steps
        )
        if not superseded:
            existing.append(record)
            continue
        if record.provenance in {"agent", "user"}:
            warnings.warn(
                f"keeping edited step-log prompt {record.id}: transcript now claims "
                f"step(s) {sorted(set(record.steps) & claimed_steps)}",
                stacklevel=2,
            )
            existing.append(record)
    by_key = {record.import_key: record for record in existing if record.import_key}
    merged = list(existing)
    seen_ids = {record.id for record in existing}
    for fresh in generated:
        old = by_key.get(fresh.import_key)
        if old:
            old.steps = fresh.steps
            old.session = fresh.session
            old.transcript = fresh.transcript
            old.message_id = fresh.message_id
            if old.provenance in {"heuristic", "step-log"}:
                old.layer, old.text, old.status = fresh.layer, fresh.text, fresh.status
            continue
        if fresh.id not in seen_ids:
            merged.append(fresh)
            seen_ids.add(fresh.id)
    write_prompts(model, merged)
    return sorted(merged, key=lambda item: (parse_time(item.ts), item.id))


def _effective_steps(
    records: list[PromptRecord], steps: list[dict]
) -> dict[str, list[dict]]:
    """Use explicit import ownership, then timestamp/session windows for agent records."""
    by_number = {int(step["n"]): step for step in steps}
    result = {
        record.id: [by_number[n] for n in record.steps if n in by_number]
        for record in records
    }
    sessions: dict[str, list[PromptRecord]] = defaultdict(list)
    for record in records:
        sessions[record.session].append(record)
    for session_records in sessions.values():
        session_records.sort(key=lambda item: parse_time(item.ts))
        for index, record in enumerate(session_records):
            if result[record.id] or record.layer != "model":
                continue
            start = parse_time(record.ts)
            end = (
                parse_time(session_records[index + 1].ts)
                if index + 1 < len(session_records)
                else None
            )
            result[record.id] = [
                step
                for step in steps
                if step.get("session") == record.session
                and parse_time(step["ts"]) >= start
                and (end is None or parse_time(step["ts"]) < end)
            ]
    return result


def _score(model: Model, owned: list[dict]) -> float:
    objects = {name for step in owned for name in step.get("objects", [])}
    params = {name for step in owned for name in step.get("params", {})}
    code_bytes = 0
    for step in owned:
        if code := step.get("code"):
            path = model.log_dir / code
            if path.is_file():
                code_bytes += path.stat().st_size
    return len(objects) * 2.0 + len(params) * 1.5 + min(code_bytes / 1000.0, 5.0)


def _session_status(model: Model, session: str, root: Path) -> str:
    runtime = next(
        (
            record
            for record in list_records(root)
            if record.model == model.name and record.session == session
        ),
        None,
    )
    if runtime:
        return "open" if runtime.desired == "running" else "closed"
    note = model.sessions_dir / f"{session}.md"
    if note.is_file():
        text = note.read_text()
        outcome = text.partition("## Outcome")[2].partition("## Next")[0].strip()
        return "closed" if outcome else "open"
    return "open"


def _connective(text: str) -> str:
    match = CONNECTIVE.match(text)
    return match.group(1).lower() if match else "next"


def _quaternion_rotate(
    rotation: list[float], vector: tuple[float, float, float]
) -> tuple[float, float, float]:
    if len(rotation) != 4:
        raise ValueError("camera rotation must be a WXYZ quaternion")
    w, x, y, z = map(float, rotation)
    vx, vy, vz = vector
    # q * v * q^-1, expanded for a unit quaternion.
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def load_cameras(model: Model, root: Path) -> dict[str, CameraRecord]:
    directory = root / ".bless" / "cameras" / model.name
    cameras = {}
    if not directory.is_dir():
        return cameras
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text())
        target = tuple(map(float, raw["target"]))
        offset = _quaternion_rotate(
            list(raw["rotation"]), (0.0, 0.0, float(raw["distance"]))
        )
        params = {
            str(key): value
            for key, value in raw.get("params", {}).items()
            if value is None or isinstance(value, (str, int, float, bool))
        }
        cameras[path.stem] = CameraRecord(
            position=tuple(target[i] + offset[i] for i in range(3)),
            target=target,
            lens_mm=float(raw["lens"]),
            locked=bool(raw.get("locked", False)),
            selection=list(raw.get("selected", [])),
            params=params,
        )
    return cameras


def _snapshot_candidates(model: Model, session: str, root: Path) -> list[Path]:
    runtime = root / ".bless" / "snapshots" / model.name / session
    paths = list(runtime.glob("*")) if runtime.is_dir() else []
    if model.out.is_dir():
        paths.extend(model.out.rglob("*"))
    if model.render.is_file():
        paths.append(model.render)
    return sorted(
        path
        for path in paths
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _snapshot_for(record: PromptRecord, model: Model, root: Path) -> str | None:
    if record.snapshot:
        supplied = Path(record.snapshot)
        path = supplied if supplied.is_absolute() else root / supplied
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            return str(path.resolve().relative_to(root.resolve()))
    candidates = _snapshot_candidates(model, record.session, root)
    if not candidates:
        return None
    prompt_time = parse_time(record.ts).timestamp()
    candidates = [
        path
        for path in candidates
        if abs(path.stat().st_mtime - prompt_time) <= 24 * 60 * 60
    ]
    if not candidates:
        return None
    runtime = root / ".bless" / "snapshots" / model.name / record.session
    nearest = min(
        candidates,
        key=lambda path: (
            0 if path.is_relative_to(runtime) else 1,
            abs(path.stat().st_mtime - prompt_time),
        ),
    )
    return str(nearest.resolve().relative_to(root.resolve()))


def build_graph(model: Model, root: Path | None = None) -> Graph:
    root = (root or bless_root()).resolve()
    records = sorted(
        read_prompts(model), key=lambda item: (parse_time(item.ts), item.id)
    )
    steps = read_steps(model)
    owned = _effective_steps(records, steps)
    scores = {
        record.id: _score(model, owned[record.id])
        for record in records
        if record.layer == "model"
    }
    maximum = max(scores.values(), default=0.0)
    cameras = load_cameras(model, root)

    versions: dict[str, int] = {}
    ordinal = 0
    for record in records:
        if record.layer == "model" and record.status == "applied":
            ordinal += 1
            versions[record.id] = ordinal
    current_id = next(
        (record.id for record in reversed(records) if record.id in versions), None
    )

    prompts: list[PromptNode] = []
    for record in records:
        node_steps = owned[record.id]
        speckle = next(
            (
                step["speckle_version"]
                for step in reversed(node_steps)
                if step.get("speckle_version")
            ),
            None,
        )
        snapshot = _snapshot_for(record, model, root)
        camera = record.camera if record.camera in cameras else None
        prompts.append(
            PromptNode(
                id=record.id,
                layer=record.layer,
                text=record.text,
                session=record.session,
                version=versions.get(record.id),
                speckle_version=speckle,
                size=(
                    round(scores.get(record.id, 0.0) / maximum, 4)
                    if record.layer == "model" and maximum
                    else (0.0 if record.layer == "model" else None)
                ),
                status=(
                    "applied"
                    if node_steps and record.status == "queued"
                    else record.status
                ),
                current=record.id == current_id or None,
                camera=camera,
                step=min((int(step["n"]) for step in node_steps), default=None),
                snapshot=snapshot,
            )
        )

    by_session: dict[str, list[PromptNode]] = defaultdict(list)
    for node in prompts:
        by_session[node.session].append(node)
    links = [
        LinkNode(
            id=f"link-{later.id}",
            text=_connective(later.text),
            **{"from": earlier.id},
            to=later.id,
        )
        for session_nodes in by_session.values()
        for earlier, later in itertools.pairwise(session_nodes)
    ]

    references = []
    prior_models: list[PromptNode] = []
    record_by_id = {record.id: record for record in records}
    for node in prompts:
        if node.layer == "model" and node.status == "applied":
            prior_models.append(node)
            continue
        if node.layer != "scene" or not prior_models:
            continue
        source = record_by_id[node.id]
        pinned = source.pinned_model
        if not pinned and (match := PIN_WORDS.search(node.text)):
            number = int(match.group(1))
            pinned_node = next(
                (
                    candidate
                    for candidate in prior_models
                    if candidate.version == number or candidate.step == number
                ),
                None,
            )
            pinned = pinned_node.id if pinned_node else None
        target = pinned or prior_models[-1].id
        references.append(
            Reference(
                id=f"ref-{node.id}",
                scene=node.id,
                model=target,
                mode="pinned" if pinned else "follows",
                text="pinned version" if pinned else "latest model",
            )
        )

    sessions = []
    for session, session_nodes in sorted(by_session.items()):
        first_index = prompts.index(session_nodes[0])
        parent = next(
            (
                candidate.id
                for candidate in reversed(prompts[:first_index])
                if candidate.layer == "model" and candidate.status == "applied"
            ),
            None,
        )
        sessions.append(
            GraphSession(
                id=session,
                status=_session_status(model, session, root),
                parent_node=parent,
            )
        )
    graph = Graph(
        model=model.name,
        sessions=sessions,
        nodes=[*prompts, *links],
        references=references,
        cameras=cameras,
    )
    payload = graph.model_dump(by_alias=True, exclude_none=True, mode="json")
    _atomic_text(graph_path(model), json.dumps(payload, indent=2) + "\n")
    return graph


def add_prompt(
    model: Model,
    session: str,
    layer: Literal["model", "scene"],
    text: str,
    now: str | None = None,
    selection: dict | None = None,
) -> PromptRecord:
    if not text.strip():
        raise ValueError("prompt text cannot be empty")
    records = read_prompts(model)
    stamp = now or iso_now()
    seed = f"{model.name}:{session}:{stamp}:{text}:{layer}"
    prompt = PromptRecord(
        id=f"p-{hashlib.sha1(seed.encode()).hexdigest()[:12]}",
        ts=stamp,
        session=session,
        layer=layer,
        text=text.strip(),
        status="queued",
        provenance="agent",
        origin="agent",
        selection=selection,
    )
    if any(record.id == prompt.id for record in records):
        raise ValueError(f"prompt id collision: {prompt.id}")
    records.append(prompt)
    write_prompts(model, records)
    return prompt


def tag_prompt(
    model: Model, prompt_id: str, layer: Literal["model", "scene"]
) -> PromptRecord:
    records = read_prompts(model)
    prompt = _find(records, prompt_id)
    prompt.layer = layer
    prompt.provenance = "user"
    if layer == "scene":
        prompt.steps = []
    write_prompts(model, records)
    return prompt


def split_prompt(
    model: Model, prompt_id: str, model_text: str, scene_text: str
) -> tuple[PromptRecord, PromptRecord]:
    if not model_text.strip() or not scene_text.strip():
        raise ValueError("both split texts are required")
    records = read_prompts(model)
    original = _find(records, prompt_id)
    original.layer = "model"
    original.text = model_text.strip()
    original.provenance = "user"
    original.split_from = prompt_id
    scene_id = f"{prompt_id}-scene"
    if any(record.id == scene_id for record in records):
        scene = _find(records, scene_id)
        scene.text = scene_text.strip()
        scene.layer = "scene"
        scene.provenance = "user"
    else:
        scene = PromptRecord(
            id=scene_id,
            ts=original.ts,
            session=original.session,
            layer="scene",
            text=scene_text.strip(),
            status="applied" if original.status == "applied" else original.status,
            provenance="user",
            origin=original.origin,
            split_from=prompt_id,
        )
        records.append(scene)
    write_prompts(model, records)
    return original, scene


def edit_prompt(model: Model, prompt_id: str, text: str) -> PromptRecord:
    if not text.strip():
        raise ValueError("prompt text cannot be empty")
    records = read_prompts(model)
    prompt = _find(records, prompt_id)
    prompt.text = text.strip()
    prompt.provenance = "user"
    write_prompts(model, records)
    return prompt


def pin_prompt(model: Model, scene_id: str, model_id: str) -> PromptRecord:
    records = read_prompts(model)
    scene = _find(records, scene_id)
    target = _find(records, model_id)
    if scene.layer != "scene" or target.layer != "model":
        raise ValueError("pin requires a scene prompt and a model prompt")
    scene.pinned_model = target.id
    scene.provenance = "user"
    write_prompts(model, records)
    return scene


def _find(records: list[PromptRecord], prompt_id: str) -> PromptRecord:
    try:
        return next(record for record in records if record.id == prompt_id)
    except StopIteration as exc:
        raise LookupError(f"no prompt {prompt_id!r}") from exc


class ReplayPlan(BaseModel):
    model_nodes: list[str]
    scene_followers: list[str]
    pinned_untouched: list[str]


def plan_replay(graph: Graph | dict, edited_node: str) -> ReplayPlan:
    """Pure replay planning: later applied models on that session, then followers."""
    graph = graph if isinstance(graph, Graph) else Graph.model_validate(graph)
    prompts = [node for node in graph.nodes if isinstance(node, PromptNode)]
    edited = next((node for node in prompts if node.id == edited_node), None)
    if edited is None:
        raise LookupError(f"no graph prompt {edited_node!r}")
    if edited.layer != "model":
        raise ValueError("replay must start from a model prompt")
    index = prompts.index(edited)
    later = [
        node.id
        for node in prompts[index + 1 :]
        if node.layer == "model"
        and node.session == edited.session
        and node.status == "applied"
    ]
    affected = {edited.id, *later}
    followers = [
        ref.scene
        for ref in graph.references
        if ref.mode == "follows" and ref.model in affected
    ]
    pinned = [ref.scene for ref in graph.references if ref.mode == "pinned"]
    return ReplayPlan(
        model_nodes=later,
        scene_followers=followers,
        pinned_untouched=pinned,
    )


def replay(
    model: Model,
    session: str,
    from_id: str | None,
    dry_run: bool,
    root: Path | None = None,
) -> ReplayPlan:
    """Plan, and unless dry, execute logged code then re-snapshot scene followers."""
    from blend import commands

    root = (root or bless_root()).resolve()
    graph = build_graph(model, root)
    candidates = [
        node
        for node in graph.nodes
        if isinstance(node, PromptNode)
        and node.layer == "model"
        and node.session == session
    ]
    if not candidates:
        raise LookupError(f"no model prompts in {model.name}/{session}")
    if from_id and from_id not in {node.id for node in candidates}:
        raise ValueError(f"prompt {from_id!r} is not a model node in {session}")
    edited = from_id or candidates[0].id
    plan = plan_replay(graph, edited)
    if dry_run:
        return plan

    records = read_prompts(model)
    steps = read_steps(model)
    effective = _effective_steps(records, steps)
    selector = f"{model.name}/{session}"
    target = commands.resolve_target(selector, root)
    client = target.bridge()
    try:
        for prompt_id in plan.model_nodes:
            for step in effective[prompt_id]:
                code_name = step.get("code")
                if not code_name:
                    continue
                path = model.log_dir / code_name
                if path.suffix == ".py":
                    prelude = (
                        "import sys\n"
                        f"sys.path.insert(0, {str(root / 'lib')!r})\n"
                        f"sys.path.insert(0, {str(model.path / 'builders')!r})\n"
                        f"__file__ = {str(path)!r}\n"
                    )
                    client.execute(prelude + path.read_text())
                elif path.suffix == ".toml":
                    import tomllib

                    values = tomllib.loads(path.read_text()).get("base", {})
                    for name, value in values.items():
                        commands.param_set(name, str(value), selector, root)
    finally:
        client.close()

    by_id = {record.id: record for record in records}
    for scene_id in plan.scene_followers:
        scene = by_id[scene_id]
        commands.snapshot(scene.camera, f"{model.name}/{scene.session}", root)
    return plan
