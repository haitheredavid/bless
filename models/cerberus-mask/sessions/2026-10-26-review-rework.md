# 2026-10-26 review-rework

## Goal
Act on the 2026-10-26 design review with layout B (shoulder version stays base).

## Steps
- Checkpoint before the rework: Speckle `a4b62fc7cd` on step 13.
- `brief.md` rewritten for layout B:
  - two parts (mask + hollow shoulder piece on a harness), necks rising behind the center ears;
  - field of view counted with the side heads in place;
  - mask ≤ 200 g, shoulder piece ≤ 600 g.
- Step 14 `review-rework`:
  - The center head gets its own parts. The side skulls are unchanged, as the review asked.
    - `CTL_Center_*` muzzle: lower and narrower, with the bridge starting inside the brow.
    - Forward nostrils, fangs and a tooth row.
    - Brow arch plus an outer cheek arch, open toward the temple like a canine orbit.
  - Vision cones are angled outward so they no longer open or detach the muzzle.
  - Pose and sizes:
    - Side Scale 0.8;
    - neck roots further back and narrower (Shoulder Forward 135, Width 300), so the necks rise behind the center ears;
    - right head back (Right Back Offset 0, Yaw Offset 15): right eye now 65° outward.
  - Center Scale stays 1.15; at 1.25 the mask was 225 g.
  - Ref gets a ghost material.
- Step 15 `build-tooling`:
  - `blend build --allow-fail` saves a failing build so it can be inspected; builder notes are printed by the CLI.
  - `checks.py`: field of view is a hard check with the side heads in place; weight is per part; failing parts list each piece's size and position.
  - Control curves are stamped with their default. Untouched ones follow changed defaults; hand edits are kept, with a warning.
  - The body drops loose fragments (a fang tip thinner than a voxel).
- Check-driven fixes along the way:
  - The cheek arch under the pupil blocked the down view (30°), so it now frames only the outer-lower corner.
  - The muzzle came loose twice: first the bridge root sat in the face cut, then the cones cut the hollow bridge.

## Outcome
- `just build cerberus-mask` passes in ~50 s.
- Field of view per eye: L 114° / R 65° outward, 86° down, 15-17° up. Mask ≤ 200 g. Mask 1 piece, Body 1, Visor 2 lenses.
- From 3/4 the center head reads as a dog or jackal skull with a brow over each eye.
- Speckle: `667e0c7ebb` on step 15 (model `26b42d6761`), published headless because the GUI was closed.
- Renders (`out/views/`):
  - hero, front, side and top are from this build (~3 min per view);
  - eyes and inside are stale, from before the rework;
  - visor isn't rendered (the job hit its 1 h limit).
- Not exported: `[export] collection = "Print"` has no parts until the sections exist.
- Workflows: new `sdf-organic-blend.md`; updated `mcp-modeling-loop`, `gn-patterns` and `sketch-to-curve`.
- Open:
  - head-on the nose still reads round (pig);
  - the sockets read better but are still mostly grille;
  - the yoke is a solid tube (~6.1 kg solid).
- Not done from the review: finer mask resolution with a measured wall (torn edges, nostril spikes), hollow yoke + harness.

## Next
- Front read of the center nose (nasal plate shape, upper lip line) and the socket rims, judged on the new renders.
- Mask resolution: finer voxels in the mask only, plus a measured minimum wall in `checks.py`.
- Hollow the yoke, add harness slots, then sections for the bed.
- Render all views in one Blender process (`blend views` opens one per view; ~5 min each before the split).
