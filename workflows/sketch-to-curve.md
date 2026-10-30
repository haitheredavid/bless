# Sketch to curve (grease pencil)

Sketch a form in grease pencil, then turn the stroke into a Control curve that GN patterns read (outline, path, profile). Use it when the user wants to draw the shape rather than describe it in numbers.

## When to use
- Organic outlines, wing edges, profiles that are easier to draw than to type.
- The user sketches in Blender (Draw mode on a GP object in Control), or the agent drafts a sketch for the user to redraw.

## Steps
1. **Sketch.** The user draws on `GP_<Name>` in Control (Blender 4.3+ GPv3). Alternatively the agent drafts one with `kit.gp.sketch("GP_Wing", [[(x, y, z), ...]])`. Re-running replaces the layer's strokes.
2. **Convert.** Run `kit.gp.to_curve("GP_Wing", "CTL_WingEdge", tolerance=0.5, kind="BEZIER")`:
   - tolerance (model units) simplifies with Ramer-Douglas-Peucker;
   - BEZIER with AUTO handles keeps it smooth and hand-editable;
   - closed is inferred when the ends meet.
3. **Feed a pattern.** Example: `outline_extrude.apply(host, Outline=bpy.data.objects["CTL_WingEdge"])`.
4. **Refine by hand.** The curve is a copy. `to_curve` won't overwrite it unless `replace=True`, so rebuilds keep the user's edits. Keep the sketch as reference (hide it), or delete it.
5. **Concept sketches as SVG.** Agent-drawn concept SVGs (1 unit = 1 mm, origin at a named anchor such as the pupils, shapes with ids) import with `bpy.ops.import_curve.svg` at true size. Stand each one on its plane through the anchor's bounding box. Set the curves to `dimensions = "2D"` and `fill_mode = "NONE"`, or the filled shapes hide the model (`"NONE"` is invalid on 3D curves). Reference: `models/cerberus-mask/builders/30_guides.py`.

## Gotchas
- **GPv3 API:**
  - `bpy.data.grease_pencils`, object type `GREASEPENCIL`;
  - layers → `frames.new(n)` → `drawing.add_strokes([counts])`;
  - points have `.position` and `.radius`.
- A GP material needs `bpy.data.materials.create_gpencil_data(mat)`, or strokes won't draw.
- Read stroke points through `obj.matrix_world`. Sketches drawn on a moved object are in its local space.

## Models
