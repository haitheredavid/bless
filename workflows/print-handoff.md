# Print handoff (to bambi)

Turn a finished model into a self-contained print pack that a printing agent (bambi: Bambu Studio + P1S) can slice without knowing how the model was built.

## When to use
- The model has a Print collection (parts split for the bed, joinery cut) and checks clean with `blend check <m> --collection Print --strict`.

## Steps
1. Fill `[print]` in `model.toml`: collection, bed (256 for the P1S), printer, material, orientation, hardware, assembly steps. The model's top-level `intent` becomes the pack's `intent` (a `[print.<Coll>] intent` overrides it for that pack).
2. Save the `.blend`, then run `just print-pack <m>`. It writes `models/<m>/print/`:
   - `parts.blend`: only the parts, modifiers baked, 1 BU = 1 mm, each on z=0, no overlaps. The exception is a part with `into` (an AMS inlay or glue-in piece): it keeps its modelled place inside its host and takes the host's rotation and move. bambi exports every visible mesh of its session `.blend`, so this file is what bambi should open as its model.
   - `stl/<part>.stl`: per-part STLs in mm.
   - `manifest.json`: the **print spec** (`print-spec/1`, bambi's `plugin/references/print-spec.md`): units, bed, material, part sizes, volumes, watertight flags, suggested plates, hardware and assembly, plus per-part intent, filaments, coupons, joints, the source commit and the feedback ids. `README.md` is the same for people.
3. The command exits non-zero if any part isn't watertight or doesn't fit the bed. It warns (yellow) about `[[print.part]]` rules that match nothing, unknown joint kinds, coupon values with no parts and `into` hosts that aren't in the pack.
4. **Lay parts flat:** `[print] flat = ["Tenon_*"]` (fnmatch globs) rotates the matching parts so their largest planar face (total area per normal) is on the bed. Use it for loose tenons, keys and pins that are modelled in place.
5. **Per-part intent, `[[print.part]]`:** fnmatch `match` (a glob or a list of globs); every matching rule applies and later rules win key by key. Keys:
   - `supports` (`none | auto | build-plate | everywhere`) and `supports_why`. bambi slices a plate with the strongest policy any part asks for.
   - `rotate = [x, y, z]` (Euler XYZ degrees), applied by print-pack before the part is dropped on the bed; `flat = true|false` per part (flat beats rotate); `orientation_why`.
   - `filament` (int, default 1), `colour` (`single | ams | glue-in | paint | engrave`) and `into` (the host part for AMS inlays or glue-in pockets; AMS inlays make bambi slice the plate as one assembled object).
6. **Filaments, `[[print.filament]]`:** `id`, `role`, `material`, `color`, `profile_hint` (a bambi filament profile name). Omit for single-material prints; `material` is the fallback.
7. **Coupons, `[[print.coupon]]`:** `id`, `param` (the builder constant it tunes, e.g. `builders/joinery.py:TENON_CLEAR`), `values`, `parts = { "0.10" = ["Coupon_C10_*"] }` and `rule` (how to pick). print-pack expands the globs to the pack's part names and leaves out coupons with no part in the pack, so a coupon lives in the pack that prints it. `bambi log fit` uses it to propose the `param` change.
8. **Joints:** builders set `obj["joints"]` on a part, a JSON string (or ID property list) shaped like the spec's `joints[]`: `{"id", "kind", "mate", "clearance_mm", "param", "coupon"}`, `kind` one of `loose-tenon | dowel | peg | key | magnet | screw | glue-face | snap`. An existing `obj["fit"]` is copied as `fit`.
9. **Extra packs:** use `blend print-pack <m> --collection Coupon` for test prints and spares. It writes to `print/coupon/` (`pack = "coupon"`). A `[print.Coupon]` table replaces orientation, flat, hardware, assembly, intent and the feedback lists, and keeps the printer, bed and material. `[[print.part]]`, `[[print.filament]]` and `[[print.coupon]]` are inherited unless the table defines its own (`[[print.Coupon.part]]` etc.), which replace them.
10. **On the bambi side** (Claude Code: the `bambi@bambi` plugin in `.claude/settings.json`; omp: `skills.customDirectories` in `.omp/config.yml` plus the `bambi` CLI on PATH):
    - `bambi init models/<m>/print` (or `models/<m>/print/coupon`) writes `session.toml` into the pack, with the spec hash;
    - bambi's `print` skill (`/bambi:print models/<m>` in Claude Code, `/skill:print models/<m>` in omp) checks, plans, slices and hands off to Bambu Studio or the printer.
    bambi owns `session.toml`, `results.json`, `thumb.png` and `out/` in the pack; re-packing never deletes them (print-pack only replaces `stl/*.stl`, `parts.blend`, `manifest.json` and `README.md`). `out/` and `check.json` are gitignored; commit `results.json`, it is the print history.

## Round trip
bambi logs every check, slice, print and coupon fit into the pack's `results.json` (`print-results/1`, bambi's `plugin/references/print-results.md`) and proposes **recommendations**: a model.toml key or a builder parameter, with a value and a reason.
1. `just print-results <m>` (`--pack coupon`, `--json`) lists the runs (slice time, grams, process, overrides; print outcome and failures; coupon picks) and every recommendation as `pending`, `applied` or `declined`. `applied, not re-packed` means the id is in model.toml but not in the pack yet. It flags a stale slice when `session.toml`'s spec hash differs from the last slice's, or when the pack was re-packed after it.
2. For each pending one, with the user: **apply** it (edit `model.toml` or the builder, rebuild) or **decline** it.
3. Record the id under `[print] feedback_applied` / `feedback_declined` (or in `[print.<Coll>]` for that pack: ids are per pack, so they never inherit).
4. Re-pack (`just print-pack <m> [--collection X]`). The new spec carries the ids, and bambi's `plan` shows them closed and the last slice stale.

## Gotchas
- **Units:** the pack is always normalised to mm, whatever the source file's units. STL has no units: slicers read the numbers as mm.
- **Viewport clipping in mm files:** Blender's view clip defaults are in BU (0.01-1000), so in mm files the far clip is 1 m. `kit.scene.fit_viewport()` (run by `build_all`) sets 0.1 mm to 10 m.
- **Plate suggestions** pack bounding rectangles, so L-shaped pieces that could nest still get a plate each. Treat them as an upper bound.
- **Inlays must stay inside their host.** Before 2026-10-21, print-pack laid every part out on its own; an `into` part landed 173 mm from its tray, and Bambu's assembled arrange failed ("ap.bed_idx -1"). Now the host and its inlays move as one group.
- **A hidden `[print] collection`** (parts that follow a display object through drivers) is revealed by `print_pack.py` before evaluating (`_common.reveal`). The file isn't changed.
- **A one-colour print of a two-body pack still needs assembling.** With one filament, bambi used to pass plain models with `--arrange`, which pulled the inlay out of the tray; with arrange off, Bambu refused ("too close to exclusion area"). bambi's `slicer.py` now uses the assemble list whenever `assemble = true`. For a one-off mono print: `bambi printer ams <pack> --write --slots N`, then map every object to filament 1 in `[objects]`.

## Models
- art-dealers-logo (2026-10-21): an AMS inlay (`Logo_Face` into `Logo_Base`) kept in place, packed from a hidden Print collection driven from a display `Logo`. It was printed all matte black (1 h 42 min, 55.6 g) when no white PLA was loaded.
- print-spec/1 (2026-10-11): intent, coupons, joints and the results.json round trip with the bambi plugin.
- witch-frame (2026-10-11): the tenons are laid flat via `flat`, plus a separate clearance-coupon pack (9 parts, 1 plate).
- witch-frame (2026-10-10): 4 corner pieces, 4 butterfly keys and 8 turn clips, 363.7 cm³, 4 suggested plates.
