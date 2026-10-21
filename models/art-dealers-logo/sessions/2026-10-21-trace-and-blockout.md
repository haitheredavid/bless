# 2026-10-21 trace-and-blockout

## Goal
Trace the logo into Control curves, build Logo_Base and Logo_Face, then show a variant grid.

## Steps
- 1 `trace-control`: `builders/trace_logo.py` traces `refs/art-dealers-logo/logo.png` into `builders/logo_trace.json`, at 150 mm wide and centred. The tracer upsamples 4×, blurs, runs marching squares, simplifies, and drops box-corner specks from the Dealers loops. `10_control.py` creates `CTL_Art` (4 loops), `CTL_Galeria` (10), `CTL_DealersText` (11) and `CTL_DealersBox` (a rectangle), only when they are missing.
- 2 `base-plate`: `GN_ArtDealers_Base` was a flat 3 mm plate (rectangle, rounded rectangle or silhouette). The shared `GN_ArtDealers_Slab` in `logo_geo.py` turns flat outlines into solids.
- 3 `raised-face`: `GN_ArtDealers_Face` combines Art + GALERIA + (box minus Dealers text), using a Manifold boolean, and lifts it to z = Base Thickness. Knockout mode cuts the letters through the box; recess mode pockets them.
- A variant grid of the first variant set built correctly. Cleared afterwards.
- 4 `open-tray`: on request, the plate became an open black tray: a 3 mm floor, a 4 mm rim and 15 mm overall. The white logo stands 12 mm tall inside it, flush with the rim. The plate shape moved into the `GN_ArtDealers_Outline` subgroup, used for both the outer outline and the inner pocket. The tray is one boolean: outer slab minus pocket. The variants are now `shallow`, `thin-rim`, `rounded`, `silhouette` and `recess`.
- 5 `galeria-bold`: added a `Galeria Bold` input (default 0.2 mm per side, max 0.25). It pushes every GALERIA outline away from the white along tangent × −Z, so strokes thicken and counters shrink. The amount is in final mm, corrected for `Logo Width`. Measured on the top faces: median stroke went from 0.84 to 1.21 mm, and the 5th percentile from 0.53 to 0.90 mm. At 0.3 mm the smallest counters fold over and the mesh stops being watertight.
- 6 `trim-slivers`: `trace_logo.py` now cuts thin parts of the white Dealers box. Light areas inside the box narrower than `MIN_STROKE` (0.8 mm) are found with an opening by a 0.4 mm-radius disk; the area outside the box counts as dark, so strips along the box edge also count as thin. Those areas are added to the Dealers cutter and carried out through the EDGE band. That removed 16 regions, 11.3 mm² in total, mostly the strips under the letter bottoms and the wedges beside the D. The logo is now centred on the bounds of Art, GALERIA and the box, and all CTL_* curves were regenerated. Re-measured with the same opening test: no white part of the box narrower than 0.8 mm is left (largest leftover under 0.05 mm²).

## Outcome
- `Logo_Base` is a tray, 168 × 53.9 × 15 mm. `Logo_Face` is 150 × 36.1 × 12 mm, from z 3 to z 15. Both are manifold. `just check` is clean.
- **AMS is required.** The black rim rises above the height where the white starts, so a single filament swap at one layer won't work.
- **Thin features: resolved.** GALERIA is ≥ 0.9 mm (5th percentile). The Dealers box has no white thinner than 0.8 mm. As a visible side effect, the letter bottoms now open through the bottom edge of the box, and the top-left corner of the box has a small notch next to the D.
- The min-stroke check from the brief is not written yet. The opening test used here is the obvious way to do it.
- **Wrap:** the steps were already builders (`10_control.py`, `20_base.py`, `30_face.py`, `logo_geo.py`, with host-side `trace_logo.py`). A clean `build_all` matched (volumes 47702 and 28897 mm³, Control unchanged). `just check`: no issues. The exports are STL and GLB per part in `exports/`. I rendered `render.png` and the `front` and `hero` views, and published Speckle version `840dd80be4` (model `d1209890e7`). There is no print pack yet.
- **Workflows:** created `image-logo-relief`; added gotchas to `gn-patterns` (Manifold solver, shared subgroup reset, `BOOL` socket kind, outline offsets).

## Next
Pick a variant (`shallow`, `thin-rim`, `rounded`, `silhouette`, `recess`) or keep the base. Add the min-stroke check (the opening test) as a builder `validate`. Then `just print-pack art-dealers-logo`, `bambi init models/art-dealers-logo/print`, and `/skill:print` with AMS.
