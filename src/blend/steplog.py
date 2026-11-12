"""Step log: every iteration step of a model, kept verbatim.

models/<m>/log/steps.jsonl has one JSON line per step; log/NNN-<slug>.py holds the code that
ran (or another snapshot, e.g. .toml params). Builders are the distilled rebuild; the log is the raw, layered history between them.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

from blend.model import Model, slugify


@dataclass
class Step:
    n: int
    slug: str
    ts: str
    intent: str = ""
    session: str | None = None
    code: str | None = None  # log-relative path of the code file
    objects: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)  # params changed by this step
    speckle_version: str | None = None
    prompt: str | None = None  # owning prompt id (bless prompt add/claim)


def _line(step: Step) -> str:
    """One JSON line; the optional prompt key is omitted when unset."""
    data = asdict(step)
    if data["prompt"] is None:
        del data["prompt"]
    return json.dumps(data) + "\n"


class StepLog:
    def __init__(self, model: Model):
        self.model = model
        self.dir = model.log_dir
        self.jsonl = self.dir / "steps.jsonl"

    def entries(self) -> list[Step]:
        if not self.jsonl.exists():
            return []
        return [
            Step(**json.loads(ln))
            for ln in self.jsonl.read_text().splitlines()
            if ln.strip()
        ]

    def append(
        self,
        slug: str,
        intent: str = "",
        code: str | None = None,
        session: str | None = None,
        objects: list[str] | None = None,
        params: dict | None = None,
        speckle_version: str | None = None,
        prompt: str | None = None,
        now: datetime | None = None,
        suffix: str = ".py",
    ) -> Step:
        """Record a step; its code (if any) goes to log/NNN-<slug><suffix> (.py, or e.g.
        .toml for a params snapshot)."""
        entries = self.entries()
        n = entries[-1].n + 1 if entries else 1
        slug = slugify(slug)
        self.dir.mkdir(exist_ok=True)
        code_name = None
        if code is not None:
            code_name = f"{n:03d}-{slug}{suffix}"
            header = f"# step {n}: {intent}\n" if intent else ""
            (self.dir / code_name).write_text(header + code.rstrip() + "\n")
        if session is None and (note := self.model.latest_session()):
            session = note.stem
        step = Step(
            n=n,
            slug=slug,
            ts=(now or datetime.now().astimezone()).isoformat(timespec="seconds"),
            intent=intent,
            session=session,
            code=code_name,
            objects=list(objects or []),
            params=dict(params or {}),
            speckle_version=speckle_version,
            prompt=prompt,
        )
        with self.jsonl.open("a") as f:
            f.write(_line(step))
        return step

    def set_speckle_version(self, version: str, n: int | None = None) -> Step:
        """Attach a Speckle version id to step n (default: the latest)."""
        entries = self.entries()
        if not entries:
            raise LookupError(f"{self.model.name} has no steps yet")
        target = (
            entries[-1] if n is None else next((s for s in entries if s.n == n), None)
        )
        if target is None:
            raise LookupError(f"no step {n}")
        target.speckle_version = version
        self.jsonl.write_text("".join(_line(s) for s in entries))
        return target

    def last(self, count: int) -> list[Step]:
        return self.entries()[-count:] if count > 0 else self.entries()
