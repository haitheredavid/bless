# 2026-10-21 one-panel-and-stage

## Goal
A simple model for family (it's their gallery logo) to tweak by hand, and render views inside Blender.

## Steps
- 7 `one-panel`: Model now holds a single object, **Logo**. `GN_ArtDealers_Logo` (`40_logo.py`) runs the base and face groups and joins them, so each setting appears once, in three panels:
  - Size: Logo Width
  - Box: Base Shape, Corner Radius, Base Margin, Rim Width, Base Thickness, Face Depth
  - Lettering: Galeria Bold, Dealers Knockout, Dealers Recess

  The Control objects are set on the group nodes, so the panel doesn't show them.
  - `Logo_Base` and `Logo_Face` moved to the **Print** collection, which is hidden and not rendered. Every input is driven from Logo's modifier (SINGLE_PROP drivers on `modifiers[...].properties.inputs.<id>.value`), so they always match the panel.
  - `build_all` clears Print too.
  - `print_pack.py` now reveals a hidden `--collection` before evaluating (`_common.reveal`).
  - `[print] collection = "Print"`. Export is now one `Logo.stl` / `Logo.glb`.
  - Materials are "Box Colour" and "Letters Colour". They are created once, and rebuilds keep colours edited by hand.
- 8 `stage`: a Stage collection (`50_stage.py`) with a grey sweep backdrop, Key and Rim sun lights (suns ignore the mm scale), a soft world, EEVEE at 1600×1000, and AgX. It also creates one camera per `[[views]]` in model.toml, fitted to the built Logo: `Cam_hero` (the scene camera), `Cam_front`, `Cam_low` and `Cam_detail`. New views `low` and `detail` were added to model.toml.
- UI: Logo is selected and framed, the viewport is in Material Preview, and Properties is on the Modifier tab. Control, Ref, Notes and Work are hidden; Control can't be selected.

## Outcome
- `just check`: Logo is 168 × 53.9 × 15 mm with no issues. Its volume (76,599 mm³) equals the base plus the face.
- Driver proof:
  - Live: Logo Width 120 / Face Depth 8 moved Logo, Logo_Base and Logo_Face together.
  - Headless: setting Logo Width to 120 and saving gave a print pack at 138 × 46.7 / 120 × 28.9. Restored to 150 and re-packed.
- **Wrap:** Blender had been closed, so I reopened it. The saved file had no hand edits (settings = `[base]`, default colours, Control intact). A clean `build_all` matched: Logo 76,599 mm³, watertight. `just check` found no issues. Exports `Logo.stl` / `Logo.glb`; rendered `render.png` and the views front, hero, low and detail. print-pack: Logo_Base 47.7 cm³ and Logo_Face 28.9 cm³, both watertight. No print recommendations. The **last slice is stale** (re-packed since then, same geometry): run `bambi init --force` and `bambi build --strict` before the next print.
- **Workflows:** `gn-patterns` (one-panel display host with driven print bodies, hidden-collection evaluation, materials kept between rebuilds); `print-handoff` (inlays kept in their host, hidden Print collection, one-colour assemble in bambi); `render-views-and-sections` (in-file Stage and cameras from `[[views]]`).
- `bambi init --force` reset the print session to the two-colour default. The one-off all-matte-black settings from the earlier print are gone; re-run `bambi printer ams --write --slots 1` for another mono print.
- Rendered `render.png` and the views front, hero, low and detail.

## Next
- Let the family play.
- Fold any settings they like back into `params.toml` (`gn.inputs(Logo.modifiers[0])`).
- Run `/wrap` to distill the one-panel-plus-driven-print-bodies pattern into `gn-patterns`.
