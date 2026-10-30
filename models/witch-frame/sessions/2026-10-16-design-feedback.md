# 2026-10-16 design-feedback

## Goal
Take the user's design feedback on the frame and improve it for the next iteration

## Feedback (first full print)
- Joints were all different sizes and hard to fit. Seam tenons were fitted per mid-side seam: N 4.3, S 6.0, E 3.5, W 3.8.
- Parts near the joints were fragile and broke during assembly. The mid-side back strip is only 8-11 mm wide.
- The mid-side joint looked unclean. Wanted joints at the corners with long pieces, and snap-in joints instead of glued tenons.
- The art stack needed real bracing; the turn clips were too weak or loose.
- Wanted more pieces per plate.
- Liked: the surface finish (PETG, no artefacts) and the form. These stay unchanged.

## Steps
<!-- `blend history witch-frame` has the full step log; summarise the arc here. -->
- Research and fit:
  - Bed: mitered rails fit the P1S on the diagonal. The long rail needs a 251.4 mm square, the short one 197.6. One long and one short rail nest on a plate with a 50 mm gap, so the rails need 2 plates instead of 4 (shapely nest).
  - Snap-fit rules for PETG: strain = 1.5·t·y/L² ≤ 3-4% when printed flat (Loftsmith, MIT manual). SnapFrames uses separate corner clips plus flex prongs.
  - The user picked spline + back bracket, flex prongs, and a coupon first.
- Fit finding: a snap spline in the miter face doesn't fit. The cove drops from 38 to 13 mm within 16 mm of the sight edge, and any socket long enough for a snap arm breaks out. The snap moved to the back key. The spline stayed only as a short alignment tenon, sitting at the sight corner above the lip.
- 13 `mitered-rails`: `40_sections` + `joinery.py` rewritten.
  - Rails: Rail_T/B/L/R come from GN_SectionPiece with non-convex miter wedges that include the 0.4 seam chamfer.
  - Key_<corner>: L key with 26 mm legs, 8 wide and 5 thick. Two in-plane snap arms (1.6 x 10, 1.2 slot) carry 0.5 barbs that catch under a 0.8 mm lip. The pocket has a hip roof, so it needs no supports.
  - Spline_<corner>: 10 x 5 x 7.5 gable tenon, 0.10 clearance.
  - Fixes along the way: GN_SectionPiece gained a final weld stage (the miter runs through the loft's corner ridge and rabbet corner, which left duplicate vertices and zero-area faces). Frame booleans now use the Manifold solver (EXACT emptied the frame on the key cut).
  - Every recess wall ≥ 2.39 mm at all 4 corners (ray check). The prong slot floors are 1.85 mm of solid bottom layers.
- 14 `flex-prongs`: `20_clips` → `20_prongs`.
  - Placement: 10 prongs, 2 per short rail at x ±75 and 3 per long rail at y 0, ±110.
  - Each prong: a 1.4 mm tongue with crush ribs (0.2 mm interference) in a gabled slot in the rabbet wall. A 14 mm arm with a bump reaches z 4.9 over the board at z 4, giving 1.3% strain nominal and 2.5% at +0.8 mm stack.
  - No screws.
- 15 `corner-coupon`: TR corner. Rail_T end with the T+75 prong slot, Rail_R end, trimmed at z 23, plus key, spline and prong. Packed to `print/coupon/` (29 cm³). Test slice in a temp copy: 51 min, 17.5 g.
- 16 `keyhole-hangers` (follow-up: the frame had no way to hang). New `25_hangers` + keyhole geometry in `joinery.py`.
  - Two keyholes in the backs of Rail_L/R at x ±122 (244 mm apart), y 117-134. Entry 9 mm, a 4.6 mm shank slot running 8 mm up, a 2.4 mm lip, and a head cavity 3.6 mm deep with a hip roof (no supports). Walls ≥ 2.39.
  - The top rail can't take one: its back strip is 8.6 mm at mid-span, and the keys fill the corners.
  - The stadium arcs use 15 segments: with 16, Rail_R's section cut left a 3-edge hole at the slot mouth.
  - Coupon_R now starts at y 113 so it keeps a whole keyhole: 31.8 cm³; test slice 55 min, 19.5 g.
  - `model.toml` gains hardware (2 screws, 244 mm apart, level) and a hang step.
- 17 `snap-tongues-centre-hanger` (user: wants the hanger centred on the top, and doubted the prongs would hold).
  - The prongs weren't glued: only friction from 0.2 mm crush ribs held each tongue. They now snap. The tongue is 5 mm deep and its two side arms (1.2 wide, freed by 0.8 slits that run 2.5 mm back into the prong) carry 0.3 mm barbs. The barbs spring into a wider pocket at the slot's end and retain on a 45° face: 1.4% strain, released by a firm pull.
  - Centred hanger: the top rail's 8.6 mm strip can't hold a keyhole, so a separate Hanger plate (40 x 22 x 3.8) sits in the clip zone behind the board.
    - It butts the top rabbet wall, which carries the frame's weight, and snaps into two slots at x ±12 with the same tongues.
    - Keyhole: 9 mm entry, 4.6 mm slot running 8 up, 1.6 mm lip. Head room is only 2.2 mm (the board's back is 4 mm from the wall), so it needs a picture nail or a wafer/truss-head screw.
    - The side keyholes are gone.
  - Checks: slot walls ≥ 2.72. No overlap with the rails. The prong bumps overlap the board proxy by design (preload). The hanger clears the board by 0.2.
  - Coupon: gains Coupon_M (Rail_T's middle with the hanger slots) and the Hanger; Coupon_R is back to its old length. 42.2 cm³; test slice 1 h 10 m, 26.8 g.
- Also changed:
  - `70_assembly` re-timed: splines → TR/BL close → halves close on the diagonal → keys → stack → prongs.
  - `50_cameras` / `[[views]]`: the clip view became prong; added a key view.
  - `model.toml [print]`: rail rotate rules (±45°), keys flipped, no hardware, new assembly steps, Coupon notes and rules.
  - Repacked `print/`: 22 parts, 361.7 cm³.

## Outcome
- **Frame:**
  - Same envelope and form: 279.4 x 355.6 x 40, sag 15, cove 1.8, 12 mm edge.
  - Four mitered rails with one identical joint set per corner (back key, alignment spline), 10 snap-in prongs for the stack, and a centred snap-in Hanger plate.
  - `check --strict` exits 0 for Model, Print and Coupon. No part intersects a rail.
- **Coupon** is ready: `print/coupon/`, one plate. Things to test:
  - the key clicks in and holds;
  - the spline closes the miter flush;
  - the prong and hanger tongues click into their slots, and the prong presses a scrap of the real backboard;
  - a nail head enters the hanger's keyhole and locks behind the lip, with Coupon_M hanging from it.
  - Log the fits with `/bambi:print-log`. The tunables are `CLEAR`, `BARB`, `ARM_*`, `SNAP_*`, `PRONG_BUMP`, `SPLINE_CLEAR` and `HANGER_*` in `joinery.py`.
- **Open: plates.**
  - Bambu's auto-arrange can't place the 356 mm rails. A test slice of the new frame pack (temp copy) failed with `Rail_R partly inside`.
  - The 2-plate nest needs locked placements, which neither `print-pack` (shelf rows; `plates_suggested` = 4 by bounding box) nor bambi (single plate, `need_arrange`) carries yet.
  - The user deferred this to a later session. Until then, place the rail plates by hand in Bambu Studio.
  - Bambu's `--load-assemble-list` supports multi-plate `need_arrange: false` with `pos_x/pos_y` (printago.io schema).
- Not yet re-rendered (views, render.png, exports). Leave that to `/wrap`.

## Next
- Print the corner coupon and log its fits, then tune `joinery.py` from the results.
- Then the locked 2-plate layout: `print-pack` nests the parts onto plates and records plate + position in the manifest, and bambi slices them through a multi-plate assemble list.
