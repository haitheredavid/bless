# Image logo to printable relief

Use this to turn a flat logo image (PNG or JPEG, light-on-dark or the reverse) into editable Control curves and a two-colour relief, plaque or open tray that prints on the P1S without thin features.

## When to use
- A user hands over a logo or wordmark as an image and wants it extruded, raised or inlaid.
- Two colours: a base in one filament, the letters in another. This includes knockout lettering, where letters are cut through a light box to show the base.

## Steps
1. **Reference.** Copy the image to `refs/<m>/logo.png` (gitignored). Measure the regions that need their own treatment from the row and column profiles of a threshold mask (`(a > 128).sum(axis)`). For example, a light box whose letters are knocked out should be traced as a rectangle plus dark letters, not as light outlines.
2. **Trace on the host, not in Blender.** Run `uv run --with pillow --with numpy --with scikit-image python models/<m>/builders/trace_logo.py`. It does the following:
   - normalises the image and masks it into groups (one per Control curve);
   - upsamples ×4 (order 3), blurs (σ 1.2 upsampled px) and pads by 1 so every contour closes;
   - runs `measure.find_contours` at 0.5, then `approximate_polygon` (tolerance 0.6);
   - drops specks below an area threshold per group, never globally, because small counters such as an A's hole are real;
   - scales to the target width, centres on bounds made from the *real* shapes (not from cutters that overshoot), and writes mm loops to `builders/logo_trace.json`, which is committed.
3. **Control from JSON.** `10_control.py` makes one curve per group with one closed POLY spline per loop, through `control.ensure`, so the curves are created only if missing. To re-trace, delete the CTL_* curves and rebuild.
4. **Solids in GN.** Object Info (ORIGINAL) → Fill Curve (`N-gons`; the default `Even-Odd` rule turns counters into holes) → extrude with an explicit offset of (0, 0, h) → join with the flipped fill → merge at 1e-4. That is `GN_ArtDealers_Slab`. Knockout: box slab minus a letters slab with Mesh Boolean (`MANIFOLD`). The letters slab runs 1 mm below and above the box, and the letters overshoot the box edges by EDGE px (`np.pad(mode="edge")` before tracing), so no faces are coplanar.
5. **Measure strokes before printing.** Check that every stroke and gap is at least 0.8 mm, the two-line minimum for a 0.4 mm nozzle. Rasterise at 0.02 mm and use either of these:
   - skeleton × 2 × distance transform for a stroke-width distribution (p5 and median). Wedge tips always read close to 0 here, so judge by percentiles;
   - `opening(mask, disk(0.4 mm))`, where the lost regions above 0.05 mm² are the real slivers. Use this one for pass or fail.
6. **Fix thin features**, cheapest first:
   - **Thin strokes:** grow the outline in GN. Use Set Position with offset `normalize(tangent × −Z) × d`, where d is in final mm × trace width / `Logo Width`. Check the sign by watching volume rise. Cap d below the point where counters fold (0.25 mm here; at 0.3 mm the mesh became non-manifold).
   - **Light slivers inside a cut box:** in the trace, find the light areas narrower than 0.8 mm with an opening, treating everything *outside* the box as dark so strips along the box edge count. Add them to the dark cutter and dilate them out through the EDGE band.
7. **Colour.** Make two bodies that meet face to face: the base gets filament 1, and the face gets filament 2 with `colour = "ams"` and `into = "<base>"`. A single filament swap at one layer only works if everything above that layer is the second colour. An open tray with a black rim breaks that, so it needs AMS.

## bpy
```python
# outward offset of every traced loop (strokes grow, counters shrink) before Fill Curve
tan = gn.node(t, "GeometryNodeInputTangent")
side = gn.node(t, "ShaderNodeVectorMath", props={"operation": "CROSS_PRODUCT"})
gn.link(t, tan, "Tangent", side, 0); side.inputs[1].default_value = (0, 0, -1)
unit = gn.node(t, "ShaderNodeVectorMath", props={"operation": "NORMALIZE"})
off = gn.node(t, "ShaderNodeVectorMath", props={"operation": "SCALE"})
gn.link(t, side, "Vector", unit, 0); gn.link(t, unit, "Vector", off, 0)
move = gn.node(t, "GeometryNodeSetPosition")
gn.link(t, info, "Geometry", move, "Geometry"); gn.link(t, off, "Vector", move, "Offset")
```
Reference implementation: `models/art-dealers-logo/builders/` (`trace_logo.py`, `10_control.py`, `logo_geo.py`, `20_base.py`, `30_face.py`).

## Gotchas
- **`find_contours` winds every loop the same way relative to the high side** (outers and holes alike). One offset sign therefore grows all strokes. The y flip into Blender mirrors this, so the sign is −Z here. Confirm it by volume.
- **Opening at the image border:** binary erosion treats outside the array as foreground, so edge strips survive. Pad explicitly: `np.pad(mask, r + 1)` for "outside is background", or `mode="edge"` when the region continues.
- **Global speck filters delete real counters.** A 25 px² threshold removed a GALERIA counter. Filter per group.
- **Scale from shape bounds, not cutter bounds.** Cutters that overshoot a box shift the centre when they change. Centre on the bounds of the light shapes plus the box.
- **Low-res sources (about 900 px wide):** the blur and simplify settings above give smooth curves at 150 mm. Expect sub-mm features to be wrong anyway, so measure (step 5) rather than trusting the look.

## Models
- art-dealers-logo (2026-10-21): 908×462 JPEG logo → a 150 mm open tray (black floor and rim, 15 mm) holding a 12 mm white logo, with "Dealers" knocked out of a white box. GALERIA was grown 0.2 mm per side (median stroke 0.84 → 1.21 mm), and 16 box slivers under 0.8 mm (11.3 mm²) were cut in the trace.
