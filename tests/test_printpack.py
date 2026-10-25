import json
from pathlib import Path

import pytest

from blend import printpack


def part(name, w, d, vol=1.0):
    return {"name": name, "size": [w, d, 5], "volume_cm3": vol, "manifold": True,
            "fits_bed": True}  # fmt: skip


def test_suggest_plates_shelf_packs_bounding_boxes():
    pieces = [part(f"P{i}", 139.7, 177.8) for i in range(4)]
    small = [part(f"K{i}", 32, 6) for i in range(4)] + [part("C", 16.5, 9)]
    plates = printpack.suggest_plates(pieces + small, 256)
    # two 139.7 x 177.8 boxes never share a 256 bed, rotated or not: 4 plates
    assert [p[0] for p in plates] == ["P0", "P1", "P2", "P3"]
    assert sum(len(p) for p in plates) == 9  # small parts fill in beside the pieces
    assert printpack.suggest_plates([part("Big", 300, 10)], 256) == [["Big"]]
    assert printpack.suggest_plates(
        [part("A", 120, 120), part("B", 120, 120)], 256
    ) == [["A", "B"]]


def test_manifest_and_readme(tmp_path):
    out = tmp_path / "models" / "m" / "print"
    res = {"blend": str(out / "parts.blend"), "stl_dir": str(out / "stl"),
           "parts": [part("Piece", 140, 178, 120.5), part("Key", 32, 6, 0.5)]}  # fmt: skip
    cfg = {"bed": 256, "material": "PLA", "hardware": ["8x M3x8"], "assembly": ["glue"]}
    m = printpack.manifest("m", res, cfg, tmp_path)
    assert m["units"] == "mm" and m["blend"] == "models/m/print/parts.blend"
    assert m["parts"][0]["stl"] == "stl/Piece.stl"
    assert m["total_volume_cm3"] == 121.0
    out.mkdir(parents=True)
    printpack.write(out, m)
    text = (out / "README.md").read_text()
    assert "| Piece | 140 x 178 x 5 | 120.5 | yes |" in text and "- 8x M3x8" in text
    assert Path(out / "manifest.json").exists()


RULES = [
    {"match": "Piece_*", "supports": "none", "supports_why": "chamfered", "colour": "single"},
    {"match": "Piece_TR", "supports": "build-plate"},
    {"match": "Clip_*", "rotate": [90, 0, 0], "orientation_why": "hook up"},
    {"match": ["Eye_L", "Eye_R"], "filament": 2, "colour": "ams", "into": "Piece_TR"},
    {"match": "Tenon_*", "flat": True},
]  # fmt: skip


def test_resolve_rules_later_entries_win_key_by_key():
    r = printpack.resolve_rules("Piece_TR", RULES)
    assert r["supports"] == "build-plate" and r["supports_why"] == "chamfered"
    assert printpack.resolve_rules("Piece_BL", RULES)["supports"] == "none"
    assert printpack.resolve_rules("Eye_R", RULES)["filament"] == 2
    assert printpack.resolve_rules("Other", RULES) == {}


def test_part_intent_orientation_supports_colour():
    tr = printpack.part_intent({"name": "Piece_TR", "flat": False}, RULES)
    assert tr["orientation"] == {"mode": "as-modelled", "rotate_deg": [0, 0, 0]}
    assert tr["supports"] == {"policy": "build-plate", "why": "chamfered"}
    assert tr["filament"] == 1 and tr["colour"] == {"method": "single"}
    clip = printpack.part_intent(
        {"name": "Clip_1", "flat": False, "rotate_deg": [90, 0, 0]}, RULES
    )
    assert clip["orientation"] == {
        "mode": "rotate", "rotate_deg": [90, 0, 0], "why": "hook up"
    }  # fmt: skip
    assert "supports" not in clip and "colour" not in clip
    tenon = printpack.part_intent(
        {"name": "Tenon_E", "flat": True, "rotate_deg": [0, 0, 0]}, RULES
    )
    assert tenon["orientation"]["mode"] == "flat"
    eye = printpack.part_intent({"name": "Eye_L", "flat": False}, RULES)
    assert eye["filament"] == 2
    assert eye["colour"] == {"method": "ams", "into": "Piece_TR"}


def test_blender_args_pass_geometry_rules_only():
    cfg = {"collection": "Print", "bed": 256, "flat": ["Key_*"], "part": RULES}
    args = printpack.blender_args(cfg)
    assert args[:4] == ["--collection", "Print", "--bed", "256"]
    assert args[4:6] == ["--flat", "Key_*"]
    rules = json.loads(args[args.index("--rules") + 1])
    assert rules == [
        {"match": "Clip_*", "rotate": [90, 0, 0]},
        {"match": ["Eye_L", "Eye_R"], "into": "Piece_TR"},
        {"match": "Tenon_*", "flat": True},
    ]
    assert "--rules" not in printpack.blender_args({"collection": "P", "bed": 1})


def test_validate_rejects_bad_rules():
    printpack.validate({"part": RULES, "filament": [{"id": 1}]})
    with pytest.raises(ValueError, match="supports must be") as e:
        printpack.validate(
            {"part": [{"match": "x", "supports": "lots", "rotate": [1, 2]}]}
        )
    assert "rotate must be" in str(e.value)
    with pytest.raises(ValueError, match="needs a match"):
        printpack.validate({"part": [{"supports": "none"}]})
    with pytest.raises(ValueError, match="integer id"):
        printpack.validate({"filament": [{"id": "1"}]})


def test_expand_coupons_to_pack_parts():
    names = ["Coupon_C10_A", "Coupon_C10_Tenon", "Coupon_C15_A"]
    coupons = [
        {"id": "tenon-E", "values": [0.1, 0.15, 0.2], "parts": {
            "0.10": ["Coupon_C10_*"], "0.15": "Coupon_C15_*", "0.20": ["Coupon_C20_*"]}},
        {"id": "elsewhere", "parts": {"1": ["Nope_*"]}},
    ]  # fmt: skip
    (c,) = printpack.expand_coupons(coupons, names)
    assert c["parts"] == {
        "0.10": ["Coupon_C10_A", "Coupon_C10_Tenon"],
        "0.15": ["Coupon_C15_A"],
        "0.20": [],
    }
    assert c["values"] == [0.1, 0.15, 0.2]


def test_manifest_v1(tmp_path):
    out = tmp_path / "models" / "m" / "print" / "coupon"
    joints = [{"id": "seam-E", "kind": "loose-tenon", "mate": "Tenon_E"}]
    res = {
        "blend": str(out / "parts.blend"), "stl_dir": str(out / "stl"),
        "parts": [
            {**part("Piece_TR", 140, 178), "flat": False, "rotate_deg": [0, 0, 0],
             "joints": joints, "fit": "snug"},
            {**part("Clip_1", 10, 6), "flat": False, "rotate_deg": [90, 0, 0]},
            {**part("Eye_L", 5, 5), "flat": False, "rotate_deg": [0, 0, 0]},
        ],
    }  # fmt: skip
    cfg = {
        "bed": 256, "material": "PETG", "part": RULES,
        "filament": [{"id": 1, "role": "body", "material": "petg"},
                     {"id": 2, "role": "eyes", "material": "pla"}],
        "coupon": [{"id": "c", "parts": {"1": ["Clip_*"]}}],
        "feedback_applied": ["rec-1"], "feedback_declined": ["rec-2"],
    }  # fmt: skip
    m = printpack.manifest(
        "m", res, cfg, tmp_path, pack="coupon", intent="fit test",
        source={"commit": "abc123", "blend": "models/m/model.blend"},
    )  # fmt: skip
    assert m["schema"] == "print-spec/1" and m["pack"] == "coupon"
    assert m["intent"] == "fit test"
    assert m["source"] == {
        "repo": "blender-sessions", "commit": "abc123", "blend": "models/m/model.blend"
    }  # fmt: skip
    tr, clip, eye = m["parts"]
    assert tr["stl"] == "stl/Piece_TR.stl" and tr["joints"] == joints
    assert tr["fit"] == "snug" and "rotate_deg" not in tr
    assert clip["orientation"]["mode"] == "rotate"
    assert eye["filament"] == 2
    assert [f["id"] for f in m["filaments"]] == [1, 2]
    assert m["coupons"] == [{"id": "c", "parts": {"1": ["Clip_1"]}}]
    assert m["feedback_applied"] == ["rec-1"] and m["feedback_declined"] == ["rec-2"]
    # v0 keys stay for old readers
    for key in ("model", "created", "units", "blend", "stl_dir", "printer", "bed_mm",
                "material", "orientation", "hardware", "assembly", "parts",
                "plates_suggested", "total_volume_cm3"):  # fmt: skip
        assert key in m
    assert printpack.lint(m, cfg) == ["[[print.part]] match='Tenon_*' matches no part"]
    out.mkdir(parents=True)
    printpack.write(out, m)
    text = (out / "README.md").read_text()
    assert "fit test" in text and "- Clip_1: rotate [90.0, 0.0, 0.0]" in text
    assert "colour ams into Piece_TR" in text and "seam-E (loose-tenon)" in text


def test_manifest_without_intent_keys(tmp_path):
    res = {"blend": str(tmp_path / "parts.blend"), "stl_dir": str(tmp_path / "stl"),
           "parts": [part("A", 10, 10)]}  # fmt: skip
    m = printpack.manifest("m", res, {}, tmp_path)
    (a,) = m["parts"]
    assert m["pack"] == "print" and "filaments" not in m and "coupons" not in m
    assert a["orientation"]["mode"] == "as-modelled" and a["filament"] == 1
    assert m["feedback_applied"] == [] and m["source"]["repo"] == "blender-sessions"


def test_lint_flags_unknown_joint_and_unused_rule(tmp_path):
    res = {"blend": str(tmp_path / "p.blend"), "stl_dir": str(tmp_path / "stl"),
           "parts": [{**part("A", 1, 1), "joints": [{"id": "j", "kind": "weld"}]}]}  # fmt: skip
    cfg = {"part": [{"match": "Z*", "supports": "none"}]}
    warn = printpack.lint(printpack.manifest("m", res, cfg, tmp_path), cfg)
    assert any("matches no part" in w for w in warn)
    assert any("'weld'" in w for w in warn)
