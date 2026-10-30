# 2026-10-26 design-review

## Goal
Design review of the blockout (no model changes); hand off a prioritised rework plan to the next modeling session.

## Steps
<!-- `blend history cerberus-mask` has the full step log; summarise the arc here. -->
- Review only, no logged steps. Inputs: `brief.md`, `sketches/*.svg`, `params.toml`, `2026-10-25-blockout.md`, `out/views/{hero,front,side}.png` (built 23:15-23:22, after step 12), the live file with `HeadProxy` hidden (restored afterwards).
- Live measures (`Heads` evaluated, split by island):

  |Island|Bounds (mm)|Volume|
  |---|---|---|
  |Centre mask shell|174 × 213 × 226, z 374-600|115 cm³ (~146 g PETG solid)|
  |Yoke + side heads|572 × 428 × 351, z 171-522|5,503 cm³ solid (~7 kg)|
  |`Visor`|109 × 24 × 47|2.9 cm³|

## Outcome
The side heads and swan necks work; the whole doesn't read as one Cerberus or one wearable yet. Findings, worst first:

1. **Two disconnected objects.** The mask floats above a shoulder ring carrying both side heads. The brief and `top.svg` want side heads merging into the centre dome. Worn, the face dog and the shoulder dogs move independently. `[base]` also breaks the brief: `Side From Collar = true` with `Full Mask = false`, but the brief says collar implies full.
2. **The centre front view reads pig/bat, not dog.** The vision cut leaves brow cap + ears + a muzzle tube. Head-on, the muzzle foreshortens to a round snout with forward-facing nostrils, and the lower piece reads as a tongue. The dog only reads in profile, but the front is the view people see.
3. **The eyes read as sunglasses.** There are no sockets: the hex grille sits under a ragged brow edge, with no lower rim or cheekbone. The brief's ≈42 × 34 mm dark sockets (the skeleton-dog reference's key feature) are gone.
4. **Inverted hierarchy.** The side heads (`Side Scale` 0.9, `Neck Extrude` 180) dominate the silhouette and are better dog skulls than the centre head. Keep the asymmetric pose (L up, R down and cocked); it's the best part.
5. **The yoke reads as an inner tube.** It's an even, featureless tube, and solid.
6. **Shell quality.** There are torn edges at the brow cut and ear bases, spikes inside both nostrils, and voxel stepping on the muzzle. Cause: `Voxel Size` 2.0 vs `Wall` 2.4, about 1 voxel per wall in the SDF difference. In the 3/4 view the muzzle hangs off the bridge as a thin strip; check it holds ≥ 1.6 mm.
7. **FOV fails its own check.** The note says R outward is 34° (blocked by the right side head) and inward 7°. `checks.py` wants outward ≥ 45°.
8. **Renders mislead.** `Ref` is in hero/front/side with the model's material. The bust (deltoid and chest blobs) is the biggest shape in every frame, so it reads as one creature, not mask-on-person. Only 3 of the 7 `[[views]]` are rendered; `eyes`, `inside`, `top` and `visor` are missing.
9. **Builders out of sync.** `builders/checks.py` (uncommitted) checks `Mask`, `Body` and `Visor`, but the live file has `Heads` + `Visor`. The Mask/Body split was started in builders but never run against `model.blend`. Line 56 of `2026-10-25-blockout.md` still lists Face Clear and Wall as "not built" (steps 10-11 built them).

Brief status:

|Requirement|Status|
|---|---|
|Eye openings ≥ 34 × 22 + sockets|openings + grille yes; sockets no|
|FOV ≥ 100° horizontal|fails on R (34° out)|
|Wall ≥ 1.6 mm|unverified; likely fails at torn edges|
|≤ 350 g|mask OK; body ~7 kg solid|
|Parts ≤ 250 mm|mask fits; 572 mm ring needs many seams|
|Strap slots, Flesh, Horn Length|not built|

Tooling:
- `look` with `distance` timed out 3/3 in this mm file. Without `distance` it works: frame close-ups with `target=["Visor"]` (or an invisible box).
- `execute_blender_code` sometimes times out at 30 s after a visibility change re-evaluates the 12 s visor. The call still runs, so re-query instead of re-running.
- Addon protocol 13 < 15: run `just addon` and restart Blender when convenient.

## Next
**Ask the user first (decision, don't pick silently):** which layout is the base?
- (A, recommended) **Temple for the half mask.** One wearable piece about 430 mm wide that matches the sketches, the bed and the weight. Start from `[variants.temple-asym]` and keep the asymmetric pose. Collar becomes the full-mask variant only.
- (B) **Collar stays base.** Then it's a two-part costume: a hollow shell yoke, a harness, and necks rising *behind* the centre ears so the silhouette closes into one beast. Set `Full Mask = true` or amend the brief.

Then, in order, one logged step each:
1. **Socket ring.** Brow ridge + cheekbone arch + lower rim around each vision opening (new `CTL_Head_Cranium` curves), so the openings read as ≈42 × 34 sockets. Make the visor black (material now, filament later). Done when the front view reads "dark eye sockets", not goggles.
2. **Centre muzzle front read.** Drop and lengthen the muzzle so the nose sits clearly below the sockets head-on. Nostrils point forward-down. Add the upper tooth row from `front.svg`. Lose the tongue read of the lower piece (half mask: no jaw). Done when a front `look` reads "dog skull" without profile help.
3. **Hierarchy.** Raise `Center Scale` or drop `Side Scale` to about 0.75-0.8, so the centre is the largest head in front and hero.
4. **FOV.** Re-pose or shrink the right head until `checks.py` passes (outward ≥ 45° per eye); the brief wants ≥ 100° horizontal.
5. **Shell resolution.** Use about 0.8 mm voxels or less in the shell region, or offset a mesh from the outer surface instead of the SDF difference. Done when there are no torn edges or nostril spikes, and wall ≥ 1.6 mm is measured (not assumed).
6. **Sync builders to the file.** Finish the `Heads` → `Mask`/`Body` split so `builders/checks.py` runs against the live file. Fix line 56 of the blockout note.
7. **Renders.** Give `Ref` a ghost/contrast material (or drop it from hero). Render all 7 views, including `eyes`, `inside` and `top`.

Leave alone: the side-head skull shapes, the swan-neck curves (`Neck Curve` 60, `Neck Taper` 0.6), and the asymmetric pose values.
