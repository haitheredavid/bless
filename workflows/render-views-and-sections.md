# Render views and sections

Named studio shots (`blend views`), matching cameras inside the .blend, and a live section cut. Use them to present a model from the angles that matter and to inspect its cross-section.

## When to use
- One `render.png` doesn't show the design: a wall piece should be seen hanging, close-ups of details, the back, or the profile.
- You need to read a profile (wall thickness, rabbet, sightwell) or show the user how parts stack.

## Steps
1. **Define shots in `session.toml`:**
   - Each `[[views]]` entry has `name`, `azimuth` (−90 = from −Y), `elevation`, and optionally `framing`, `size`, `upright`, `include`, `zoom` and `target`.
   - `upright = true` stands the model up (+Z face turned to −Y), like a frame on a wall.
   - `include = ["Ref"]` adds proxy meshes (art, glazing) that a normal render skips.
   - `zoom` + `target` (model coordinates) crop in on a detail.
2. **Render:** `just views <s>` (or `--only NAME`) writes `out/views/<name>.png`. Tile them for a quick review with `ffmpeg ... tile=4x2`.
3. **Add matching cameras to the .blend** (`builders/50_cameras.py`) so the user can press Ctrl+Numpad0 on `Cam_<name>`. For upright views, rotate the direction back with `(x, y, z) → (x, z, −y)` and use +Y as the camera's up. To let people render with F12 inside Blender, also build a Stage collection: a sweep backdrop sized from the model, sun lights (they don't care about mm scale, unlike area lights), a world, and EEVEE. Read the cameras straight from `model.toml` `[[views]]` (azimuth, elevation, zoom, target), so the in-file shots and `blend views` stay the same. Reference: `models/art-dealers-logo/builders/50_stage.py`.
4. **Live section (`builders/60_section.py`):**
   - Copy the parts into a `Section` collection under an offset root.
   - Each copy gets a boolean against a half-space box parented to a `Section_Plane` empty. The user moves or rotates the empty to move the cut.
   - Cut faces turn red with `material_mode = "TRANSFER"`, *and* the cut material must already sit in a slot on each copy (`obj.data = src.data.copy(); obj.data.materials.append(cut)`). Otherwise the viewport draws them grey.
   - Orthographic cameras parented to the plane look at the cut.

## bpy
```python
# upright view direction -> camera in the .blend (frame lying flat)
d = Vector((cos(a) * cos(e), sin(a) * cos(e), sin(e)))
d, up = Vector((d.x, d.z, -d.y)), Vector((0, 1, 0))
z = d.normalized()
x = up.cross(z).normalized()
m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
m.translation = target + z * dist
```

## Gotchas
- **Offset the section copy toward the camera side** (cameras look from −X, so offset −X). Otherwise the real model blocks the view of the cut.
- **The zoom crop must be a cube around the target** (radius / zoom). Per-axis extents shrink thin axes (frame depth) to nothing.
- **`render.png` and the gallery still use the flat, Model-only still.** Point people at `out/views/hero.png` for wall pieces.
- **mm sessions need the viewport clip range scaled.** Defaults are 1000 BU = 1 m; `setup_scene.py` now scales it. Cameras need `clip_end` in mm too.
- **Fit stage cameras to the evaluated mesh at build time.** They don't follow later size changes, so rerun `build_all` after big parameter changes.

## Models
- witch-frame (2026-10-10): added `blend views` (hero, front, profile, plan, back, corner, clip), `Cam_*` cameras and a red-capped live section of frame + clips + art stack.
- art-dealers-logo (2026-10-21): Stage collection plus `Cam_hero/front/low/detail` generated from `[[views]]`, so the family can render with F12.
