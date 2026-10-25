---
created: 2026-10-21
---
# art-dealers-logo

## Intent
A 150 mm desk block of the Art Dealers Galeria logo, printed on the P1S as one part in two colours. The black part is an open tray: a floor plus a rim wall. Inside it, "Art", "GALERIA" and the "Dealers" box stand up in white to the height of the rim, so the black reads as the box and the white as its contents. The "Dealers" letters are cut through the white box so the black floor shows through them, as in the reference (`refs/art-dealers-logo/logo.png`, 908×462).

## Requirements
- mm units, Z up, resting on z=0.
- Logo width is 150 mm (≈ 0.265 mm per reference pixel). The tray is 168 × 53.9 × 15 mm with an 8 mm margin, so it prints in one piece on the 256 mm bed.
- Floor 3 mm. Rim 4 mm wide, leaving a 4 mm gap between the rim and the logo. Interior depth (`Face Depth`) 12 mm, and the white logo is flush with the top of the rim.
- Two colours, one part, and **AMS is required**. `Logo_Face` (filament 2) sits in `Logo_Base` (filament 1). The rim is black above the floor, so a single filament swap at one layer height won't work.
- Minimum stroke and gap 0.8 mm: GALERIA strokes and the gaps in the "Dealers" letters are close to this. A check enforces it.
- Both bodies watertight. They meet face to face, with no overlap.
- No supports.

## Plan
**Control** (user-owned closed curves, created from `builders/logo_trace.json` only if missing):
- `CTL_Art`, `CTL_Galeria`, `CTL_DealersText`: the letter outlines, including their holes.
- `CTL_DealersBox`: the light rectangle behind "Dealers".
- The plate outline is derived in GN from the logo bounds or hull, so it has no Control curve.

**Trace:** `builders/trace_logo.py` (host-side; `uv run --with pillow --with numpy --with scikit-image python ...`) thresholds the reference, upsamples it, finds the contours and simplifies them into POLY loops at 150 mm wide, centred on the origin. Re-run it and delete the CTL_* curves to re-trace.

**Parts:**
| Object | Node group | Technique | Builder |
|---|---|---|---|
| `Logo_Base` | `GN_ArtDealers_Base` | open tray: the outer outline as a slab of height Base Thickness + Face Depth, minus a pocket from the same outline grown Rim Width less, with its bottom at Base Thickness. `GN_ArtDealers_Outline` gives a rectangle, a rounded rectangle, or the convex hull grown by Grow | `builders/20_base.py` |
| `Logo_Face` | `GN_ArtDealers_Face` | Art + GALERIA (outlines grown by `Galeria Bold`, 0.2 mm per side, so its strokes are ≥ 0.9 mm) + (box minus Dealers text, Manifold boolean), extruded `Face Depth` from the floor top; in recess mode the text is pocketed `Dealers Recess` | `builders/30_face.py` |

Shared helpers (the slab group, logo scale, materials) are in `builders/logo_geo.py`.

**Variants:** `shallow`, `thin-rim`, `rounded`, `silhouette`, `recess` (see `params.toml`).

**Checks:** both bodies watertight, envelope within 256 mm, and minimum feature size of at least 0.8 mm. Views: `front` (top-down, compared with the reference), `hero` (¾), `low` and `detail`.

**Playing with it:** the Model collection holds one object, `Logo`, built by `40_logo.py` (`GN_ArtDealers_Logo`). All settings are on its modifier, in the Size, Box and Lettering panels. The print bodies `Logo_Base` and `Logo_Face` live in the hidden Print collection and are driven from Logo, so they always match it. The colours are the "Box Colour" and "Letters Colour" materials. The Stage collection (`50_stage.py`) holds the backdrop, lights and `Cam_<view>` cameras: select a camera, press Ctrl+Numpad0 to look through it, and F12 to render.

**First session:** trace the Control curves and check them against the reference, build the base and face, then show a variant grid of the four variants.

## Lessons
- At 150 mm the traced GALERIA strokes are about 0.84 mm (5th percentile 0.53 mm), too thin for 12 mm tall fins, so `Galeria Bold` 0.2 grows them to about 1.21 mm. Keep `Galeria Bold` at or below 0.25; at 0.3 the A and R counters fold.
- The light "Dealers" box had sub-0.8 mm slivers under the letter bottoms and beside the D. The trace now adds them to the cutter, which opens the letter bottoms through the box edge. If `Logo Width` grows a lot, re-run the trace with a smaller `MIN_STROKE` to keep more of the box.
- The open tray rules out a single filament swap at one layer, so this model needs AMS.
