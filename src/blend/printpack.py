"""Print pack: the handoff from a model to a printing agent (e.g. bambi).

`blend print-pack <m>` bakes the Print collection into models/<m>/print/:
parts.blend (mm, parts only, on the bed), stl/<part>.stl, manifest.json and README.md.
The manifest carries units, the bed, material, hardware, assembly notes and a suggested
plate grouping; the printing agent owns the final layout and slicing.

The manifest is a `print-spec/1` (bambi: plugin/references/print-spec.md): on top of the
v0 keys it carries intent per part (orientation, supports policy, filament, colour method,
joints), filaments, coupons and the recommendation ids the model applied or declined.
model.toml's [[print.part]] rules (fnmatch `match`, later entries win key by key) set the
per-part intent; bambi turns it into slice settings.
"""

import json
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

SCHEMA = "print-spec/1"
GAP = 5.0  # mm between parts when suggesting plates
SUPPORT_POLICIES = ("none", "auto", "build-plate", "everywhere")
COLOUR_METHODS = ("single", "ams", "glue-in", "paint", "engrave")
JOINT_KINDS = (
    "loose-tenon",
    "dowel",
    "peg",
    "key",
    "magnet",
    "screw",
    "glue-face",
    "snap",
)
# [[print.part]] keys print_pack.py (Blender) needs to place a part ("into": AMS inlays and
# glue-in pieces stay where they were modelled relative to their host)
GEOMETRY_KEYS = ("match", "flat", "rotate", "into")


def _globs(match) -> list[str]:
    return [match] if isinstance(match, str) else list(match)


def matches(name: str, match) -> bool:
    return any(fnmatch(name, g) for g in _globs(match))


def validate(cfg: dict) -> None:
    """Raise ValueError listing malformed [[print.part]] / [[print.filament]] /
    [[print.coupon]] entries."""
    bad = []
    for i, rule in enumerate(cfg.get("part", []), 1):
        where = f"[[print.part]] #{i}"
        if "match" not in rule:
            bad.append(f"{where} needs a match glob")
        if rule.get("supports", "none") not in SUPPORT_POLICIES:
            bad.append(
                f"{where}: supports must be one of {', '.join(SUPPORT_POLICIES)}"
            )
        if rule.get("colour", "single") not in COLOUR_METHODS:
            bad.append(f"{where}: colour must be one of {', '.join(COLOUR_METHODS)}")
        rot = rule.get("rotate", [0, 0, 0])
        if not (
            isinstance(rot, list)
            and len(rot) == 3
            and all(isinstance(a, int | float) for a in rot)
        ):
            bad.append(f"{where}: rotate must be [x, y, z] degrees")
        if not isinstance(rule.get("filament", 1), int):
            bad.append(f"{where}: filament must be an integer")
    for i, fil in enumerate(cfg.get("filament", []), 1):
        if not isinstance(fil.get("id"), int):
            bad.append(f"[[print.filament]] #{i} needs an integer id")
    for i, c in enumerate(cfg.get("coupon", []), 1):
        if not c.get("id"):
            bad.append(f"[[print.coupon]] #{i} needs an id")
        if not isinstance(c.get("parts", {}), dict):
            bad.append(f"[[print.coupon]] #{i}: parts must be a table of value = globs")
    if bad:
        raise ValueError("\n".join(bad))


def resolve_rules(name: str, rules: list[dict]) -> dict:
    """Merge every [[print.part]] rule matching `name`; later rules win key by key."""
    merged: dict = {}
    for rule in rules:
        if matches(name, rule.get("match", [])):
            merged.update({k: v for k, v in rule.items() if k != "match"})
    return merged


def geometry_rules(cfg: dict) -> list[dict]:
    """The [[print.part]] keys print_pack.py applies in Blender (match, flat, rotate, into)."""
    out = []
    for rule in cfg.get("part", []):
        r = {k: rule[k] for k in GEOMETRY_KEYS if k in rule}
        if len(r) > 1:
            out.append(r)
    return out


def blender_args(cfg: dict) -> list[str]:
    """print_pack.py arguments for a print_options() config."""
    args = ["--collection", cfg["collection"], "--bed", str(cfg["bed"])]
    for pat in cfg.get("flat", []):
        args += ["--flat", pat]
    if rules := geometry_rules(cfg):
        args += ["--rules", json.dumps(rules)]
    return args


def part_intent(part: dict, rules: list[dict]) -> dict:
    """Per-part print-spec/1 intent: orientation, supports, filament, colour.
    `part` is print_pack.py's result (flat, rotate_deg as applied in Blender)."""
    rule = resolve_rules(part["name"], rules)
    rotate = [
        float(a) for a in part.get("rotate_deg") or rule.get("rotate") or (0, 0, 0)
    ]
    if part.get("flat"):
        mode, rotate = "flat", [0.0, 0.0, 0.0]
    elif any(rotate):
        mode = "rotate"
    else:
        mode = "as-modelled"
    out: dict = {"orientation": {"mode": mode, "rotate_deg": rotate}}
    if why := rule.get("orientation_why"):
        out["orientation"]["why"] = why
    if "supports" in rule:
        out["supports"] = {"policy": rule["supports"]}
        if why := rule.get("supports_why"):
            out["supports"]["why"] = why
    out["filament"] = int(rule.get("filament", 1))
    if "colour" in rule:
        out["colour"] = {"method": rule["colour"]}
        if into := rule.get("into"):
            out["colour"]["into"] = into
    return out


def expand_coupons(coupons: list[dict], names: list[str]) -> list[dict]:
    """[[print.coupon]] with each value's part globs expanded to the pack's part names.
    Coupons with no part in this pack are left out (they belong to another pack)."""
    out = []
    for c in coupons:
        parts = {
            str(value): [n for n in names if matches(n, globs)]
            for value, globs in c.get("parts", {}).items()
        }
        if c.get("parts") and not any(parts.values()):
            continue
        out.append({**c, "parts": parts})
    return out


def lint(m: dict, cfg: dict) -> list[str]:
    """Warnings worth showing after a pack: unused rules, unknown joint kinds, etc."""
    names = [p["name"] for p in m["parts"]]
    warn = []
    for rule in cfg.get("part", []):
        if not any(matches(n, rule["match"]) for n in names):
            warn.append(f"[[print.part]] match={rule['match']!r} matches no part")
    ids = {f["id"] for f in m.get("filaments", [])}
    for p in m["parts"]:
        if ids and p.get("filament", 1) not in ids:
            warn.append(
                f"{p['name']}: filament {p['filament']} not in [[print.filament]]"
            )
        for j in p.get("joints", []):
            if j.get("kind") not in JOINT_KINDS:
                warn.append(
                    f"{p['name']}: joint {j.get('id')!r} kind {j.get('kind')!r}"
                )
        into = (p.get("colour") or {}).get("into")
        if into and into not in names:
            warn.append(f"{p['name']}: colour into {into!r} is not a part in this pack")
    for c in m.get("coupons", []):
        for value, got in c["parts"].items():
            if not got:
                warn.append(f"coupon {c['id']} {value}: no part matches")
    return warn


def suggest_plates(parts: list[dict], bed: float, gap: float = GAP) -> list[list[str]]:
    """Conservative plate grouping: shelf-pack bounding rectangles (rotation allowed)
    onto bed x bed plates, largest first. Real layouts can nest shapes tighter (L-shaped
    pieces); the printing agent does the final arrange."""
    plates: list[dict] = []  # {"shelves": [[y, height, used_x]], "top": y, "names": []}

    def place(plate, w, d) -> bool:
        for shelf in plate["shelves"]:
            _, h, used = shelf
            if d <= h and used + w <= bed:
                shelf[2] = used + w + gap
                return True
        if plate["top"] + d <= bed and w <= bed:
            plate["shelves"].append([plate["top"], d, w + gap])
            plate["top"] += d + gap
            return True
        return False

    for p in sorted(parts, key=lambda p: -max(p["size"][:2])):
        w, d = p["size"][:2]
        for plate in plates:
            if place(plate, w, d) or place(plate, d, w):
                plate["names"].append(p["name"])
                break
        else:
            plate = {"shelves": [], "top": 0.0, "names": [p["name"]]}
            if not (place(plate, w, d) or place(plate, d, w)):
                plate["names"] = [p["name"]]  # larger than the bed: its own plate
            plates.append(plate)
    return [p["names"] for p in plates]


def manifest(
    model: str,
    result: dict,
    cfg: dict,
    root: Path,
    *,
    pack: str = "print",
    intent: str = "",
    source: dict | None = None,
) -> dict:
    bed = float(cfg.get("bed", 256))
    rules = cfg.get("part", [])
    parts = [
        {
            **p,
            "stl": f"{Path(result['stl_dir']).name}/{p['name']}.stl",
            **part_intent(p, rules),
        }
        for p in result["parts"]
    ]
    for p in parts:
        p.pop("rotate_deg", None)  # lives in orientation now
    names = [p["name"] for p in parts]
    m = {
        "schema": SCHEMA,
        "model": model,
        "pack": pack,
        "intent": intent,
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {
            "repo": "blender-sessions",
            "commit": "",
            "blend": "",
            **(source or {}),
        },
        "units": "mm",
        "blend": str(Path(result["blend"]).relative_to(root)),
        "stl_dir": str(Path(result["stl_dir"]).relative_to(root)),
        "printer": cfg.get("printer", ""),
        "bed_mm": bed,
        "material": cfg.get("material", "PLA"),
        "orientation": cfg.get(
            "orientation", "as modelled: each part's lowest face is on the bed (z=0)"
        ),
        "hardware": list(cfg.get("hardware", [])),
        "assembly": list(cfg.get("assembly", [])),
        "parts": parts,
        "plates_suggested": suggest_plates(parts, bed),
        "total_volume_cm3": round(sum(p["volume_cm3"] for p in parts), 1),
        "feedback_applied": list(cfg.get("feedback_applied", [])),
        "feedback_declined": list(cfg.get("feedback_declined", [])),
    }
    if filaments := cfg.get("filament"):
        m["filaments"] = [dict(f) for f in filaments]
    if coupons := cfg.get("coupon"):
        m["coupons"] = expand_coupons(coupons, names)
    return m


def _intent_line(p: dict) -> str:
    o = p["orientation"]
    bits = [o["mode"] + (f" {o['rotate_deg']}" if o["mode"] == "rotate" else "")]
    if s := p.get("supports"):
        bits.append(f"supports {s['policy']}")
    bits.append(f"filament {p['filament']}")
    if c := p.get("colour"):
        bits.append(
            f"colour {c['method']}" + (f" into {c['into']}" if "into" in c else "")
        )
    if j := p.get("joints"):
        bits.append(
            "joints " + ", ".join(f"{x.get('id')} ({x.get('kind')})" for x in j)
        )
    return f"- {p['name']}: " + "; ".join(bits)


def readme(m: dict) -> str:
    rows = "\n".join(
        f"| {p['name']} | {' x '.join(f'{v:g}' for v in p['size'])} | {p['volume_cm3']} "
        f"| {'yes' if p['manifold'] else 'NO'} |"
        for p in m["parts"]
    )
    plates = "\n".join(
        f"{i}. {', '.join(names)}" for i, names in enumerate(m["plates_suggested"], 1)
    )
    lists = {
        k: "\n".join(f"- {v}" for v in m[k]) or "- none"
        for k in ("hardware", "assembly")
    }
    intents = "\n".join(_intent_line(p) for p in m["parts"])
    coupons = "\n".join(
        f"- {c['id']}: {c.get('param', '')} values {c.get('values', [])}; {c.get('rule', '')}"
        for c in m.get("coupons", [])
    )
    return f"""# {m["model"]}: print pack

{m.get("intent") or ""}

Generated by `blend print-pack` ({m["created"]}), spec `{m.get("schema", "v0")}`. Units **{m["units"]}** (1 Blender unit
= 1 mm). Material {m["material"]}. Bed {m["bed_mm"]:g} mm.

- `parts.blend`: only the printable parts, modifiers applied, each on the bed (z=0), laid
  out without overlaps. Open it as the printing session's model.
- `stl/`: one STL per part (mm).
- `manifest.json`: this information, machine-readable.

Orientation: {m["orientation"]}.

| part | size (mm) | volume (cm³) | watertight |
|---|---|---|---|
{rows}

Total volume {m["total_volume_cm3"]} cm³.

## Suggested plates
Conservative shelf packing of bounding boxes (rotation allowed); nesting the L-shaped
pieces may need fewer plates. The printing agent arranges and slices.

{plates}

## Per-part intent
{intents}
{("\n## Coupons\n" + coupons + "\n") if coupons else ""}
## Hardware
{lists["hardware"]}

## Assembly
{lists["assembly"]}
"""


def write(out: Path, m: dict) -> None:
    (out / "manifest.json").write_text(json.dumps(m, indent=2) + "\n")
    (out / "README.md").write_text(readme(m))
