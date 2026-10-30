# SDF organic blend

Organic forms (heads, skulls, necks, creatures, wearable shells) built from Control Bezier curves whose point radius is the local thickness, unioned as one SDF and filleted where parts meet. Shells around a body proxy and cutouts (eye openings, sockets, nostrils) are SDF booleans. Use it for anything sculpted that should stay parametric and printable; sweeps and extrusions belong to `gn-patterns.md`.

## When to use
- Characters, animal heads, masks, creature props: forms that are easier to describe as "a blob here, this thick" than as profiles.
- A wearable that must clear a body: hollow shell = form minus (proxy + clearance) minus its own inside.

## Steps
1. **Blob curves in Control.** One collection per part (`Control/CTL_Head/CTL_Head_<Part>`).
   - Each curve is a Bezier through (x, y, z, radius) points in a part-local frame. The radius is the thickness: Alt+S in Edit Mode.
   - Mirrored pairs are `_L`/`_R`.
   - Create them with `blob_geo.blob(name, coll, pts, mirror_x)`. It stamps each curve with a fingerprint of its default, so untouched curves follow changed defaults and hand edits are kept, with a warning.
2. **Blob group** `GN_SDFBlob`:
   - Curve to Points (spacing = voxel/2), with the `radius` attribute as the point radius.
   - Points to SDF Grid → Grid to Mesh → **Mesh to SDF Grid (band 6)**: re-banding before the fillet.
   - SDF Grid Fillet (iterations = blend) → SDF Grid Mean (smoothing) → Grid to Mesh → Set Shade Smooth.
3. **Rig, then parts.**
   - One cheap rig group poses every part's curves into world space and **tags points** with booleans: `center` (which part they belong to), `cut` (subtract, don't add), `vision` (what the visor follows). Store Named Attribute, POINT domain.
   - Each printable part is its own object and group. It reads the rig through Object Info (ORIGINAL) and Separate Geometry by tag, then blends.
   - A part's group has only its own inputs, so an edit re-evaluates only the parts that use it.
4. **Cutters ride along.** Cutter curves (sockets, nostrils, vision cones) are joined to their head before posing, so every pose and scale moves them too. After the blend: `Difference(body SDF, cutter SDF)`, with the cutters blended at Fillet 0.
5. **Wearable shell** = `Difference(form, form offset -Wall, proxy SDF offset +Face Clear, back-clip box, cutters)`.
   - Then drop loose fragments: Mesh Island + Accumulate face area per island; delete islands under 25% of the biggest.
   - Cutters that must stay on the wearer (eye openings) are left out of the part's scale (Center Scale), so they stay on the pupils.
6. **Thin insert behind an opening** (eye grille visor):
   - Plate = proxy SDF offset by Face Clear minus by Face Clear - Thick, at a finer voxel on a clipped region of the proxy (Mesh Boolean INTERSECT, MANIFOLD).
   - Trim it to the openings grown by a glue margin with a **mesh** boolean (see Gotchas).
   - Perforate with instanced cylinders on staggered point grids (hex) via Mesh Boolean DIFFERENCE.
7. **Checks as code.** `builders/checks.py` runs after params in `build_all` and fails the build on:
   - pieces per part, with each piece's position;
   - open edges;
   - field of view raycast from the eyeball centres through every part;
   - weight per part.
   Build headless with `just build <m>`; use `--allow-fail` to save a failing state for inspection.

## bpy
```python
# models/cerberus-mask/builders/blob_geo.py has the full set; the core of GN_SDFBlob:
pts = gn.node(t, "GeometryNodeCurveToPoints", props={"mode": "LENGTH"})          # Length = voxel/2
rad = gn.node(t, "GeometryNodeInputNamedAttribute", props={"data_type": "FLOAT"}, Name="radius")
sdf = gn.node(t, "GeometryNodePointsToSDFGrid")                                   # Points, Radius, Voxel Size
raw = gn.node(t, "GeometryNodeGridToMesh")                                        # re-band: mesh ...
band = gn.node(t, "GeometryNodeMeshToSDFGrid", Band_Width=6)                      # ... back to SDF
fil = gn.node(t, "GeometryNodeSDFGridFillet")                                     # now safe to fillet
```

## Gotchas
- **Points to SDF Grid leaves a band too thin for Fillet/Mean.** They tore the mesh: 8.9k non-manifold edges and 165 islands on a head. Offset(+r)/Offset(-r) closing tears too. Fix: Grid to Mesh → Mesh to SDF Grid (band 6) before filleting. This costs ~0.2 s at 3 mm voxels.
- **SDF Grid Boolean INTERSECT of a thin plate with a big region returned half the region** (565 cm³ instead of 3). Do that trim as a Mesh Boolean (MANIFOLD) on closed meshes.
- **SDF offsets must stay inside the narrow band.** Offsetting by 6-8 mm needs Band Width ≥ offset/voxel (24 at 0.5 mm voxels).
- **Thin parts need a stronger blend.** Ears, mandibles and fangs at radius 7-12 mm read as separate rods at Fillet 4; Fillet 12 / Smooth 3 at 2 mm voxels melts them, at ~0.8 s per evaluation.
- **Wall vs voxel.** A 2.4 mm wall at 2 mm voxels is about one voxel: torn edges at cuts and spikes in nostrils. Use voxels ≤ Wall/3 for the shell part.
- **Cutters vs hollow parts.** A cone whose edge passes inside a hollow tube cuts its 2.4 mm wall apart, and the part comes loose (the cerberus muzzle, twice). Keep cutter edges clear of bridges by more than the wall, and anchor bridges inside solid mass (the brow) rather than near the face cut.
- **Cutters vs view.** Bone arches under the pupil block the downward view (30° instead of 60°). Frame openings above and at the outer-lower corner only; leave the orbit open toward the temple (as on a real canine skull).
- **Thin tips under one voxel** (a fang tip at 1.2 mm × 0.8 scale) come out as 6-face islands. Drop fragments in every part, not just the shell.
- **Mesh Boolean MANIFOLD returned nothing** when its input was empty because the proxy object had lost its geometry upstream. An empty operand looks like a solver failure: probe the inputs first.
- **Object Info on an object in a hidden collection** evaluates to nothing. A rig in Work must stay visible (`20_heads.py` re-shows Work).

## Models
- cerberus-mask (2026-10-25/26):
  - three dog heads (center half mask + two on necks from a shoulder yoke), head proxy, tagged cutters, hex-grille visor;
  - split into Rig + Mask/Body/Visor groups;
  - `checks.py` for field of view, pieces and weight.
