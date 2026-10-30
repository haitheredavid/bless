# GN patterns

Build a model as a stack of Geometry Nodes pattern modifiers on a host object, driven by Control curves. The user can reshape the curves and turn the modifier knobs by hand, and rebuilds keep both.

## When to use
- Any form that is a sweep, an extruded outline or a pocketed solid: frames, mouldings, rims, plaques, trays, rabbets, recesses.
- Whenever the user wants to "experiment with X". Expose X as an input, then compare variants.

## Steps
1. **Control first.** Create the inputs once with `kit.control.ensure`:
   - `control.rect` for an outline or path;
   - `control.profile` for a cross-section (X across the path, Y up);
   - `control.curve(..., kind="BEZIER")` for shapes the user will pull by hand.
2. **Host + patterns.** Call `gn.host("Frame")`, then chain patterns. Each `apply` adds (or reuses) one modifier:
   ```python
   from kit import control, gn
   from patterns import outline_extrude, pocket_cut, profile_sweep

   outline = control.ensure("CTL_Outline", lambda n: control.rect(n, 280, 356, radius=12))
   body = gn.host("Body")
   outline_extrude.apply(body, Outline=outline, Height=30, Taper=0.95)
   pocket_cut.apply(body, Pocket_Width=254, Pocket_Height=330, Pocket_Depth=8)
   ```
   Keyword args set inputs by socket name, with `_` for spaces.
3. **Params.** Move the values you want to tune into `params.toml [base]`. `build_all.py` applies them last. Add `[variants.<v>]` overrides for the options to compare.
4. **Compare.**
   - Live: `params.grid()`, then `look`, then `params.clear_grid()`.
   - Rendered: `just` → `uv run blend variants <m>` writes `out/variants.png`.
5. **Readable trees.** Wrap each step of a builder in `with gn.stage(t, "1 · Outline ring"):`. `gn.arrange(t)` then lays the stages out left to right, each in a labelled, tinted Frame box, so the tree reads like the builder. Number the labels in flow order.
6. **New pattern.** When a model-specific node tree proves reusable, move it to `lib/patterns/<name>.py` with `NAME`, `build(reset)` and `apply`. Add it to `patterns.ALL` and run `uv run blend patterns-lib`.
7. **One panel for people who aren't modellers.** When a model has several hosts (for example one body per print colour), add a display host whose group (`GN_<Model>_<Name>`) runs the part groups as group nodes and joins them. Expose each shared input once, grouped with `t.interface.new_panel("Box")` and `t.interface.move_to_parent(sock, panel, i)`. Set the Control objects as defaults on the group-node sockets, so they don't show in the panel. Keep the part hosts in the hidden Print collection, and drive every non-object input from the display host:
   ```python
   slot = getattr(part_mod.properties.inputs, item.identifier)  # Blender 5 input storage
   fc = slot.driver_add("value"); fc.driver.type = "AVERAGE"
   var = fc.driver.variables.new(); var.targets[0].id = display_obj
   var.targets[0].data_path = getattr(mod.properties.inputs, gn.socket_id(t, item.name)).path_from_id("value")
   ```
   The print parts then always match what's on screen, live and headless. Point `[print] collection` at Print (print-pack reveals it). Reference: `models/art-dealers-logo/builders/40_logo.py`.

## Patterns
| module | group | inputs |
|---|---|---|
| `profile_sweep` | GN_ProfileSweep | Path, Profile, Scale, Fill Caps, Smooth |
| `outline_extrude` | GN_OutlineExtrude | Outline, Height, Taper, Fillet |
| `pocket_cut` | GN_PocketCut | Pocket Width/Height/Depth/Bottom/Corner Radius/Center |
| `section_piece` | GN_SectionPiece | Source, Box Min, Box Max, Cutter |
| `frame_loft` | GN_FrameLoft (+ GN_LoftBand) | Outline, Sag, Tip Shape, Edge Height, Depth, Face Power, Sight/Rabbet Width/Height, Rabbet Depth, Samples, Face Rings, Material |

## Lofts (GN_FrameLoft)
- A freeform outline lofted into a rectangular opening can't be a sweep, because the opening would follow the outline. Instead, loft equal-count point rings with `GN_LoftBand`: a grid of (count+1) × rows, positions sampled by index, z shaped by Power. Chain the bands around the cross-section and merge them.
- Corner correspondence: build every ring as a subdivided Quadrilateral (top-right first, CCW). The outline ring is its bounding-box rectangle **projected** (Geometry Proximity, edges) onto the Control curve. A Bezier with VECTOR handles evaluates to just its corners, so index-sampling the curve itself doesn't work.
- Grid vertex index = x × Vertices Y + y.

## Gotchas
- **Blender 5 moved modifier inputs** from ID properties (`mod["Socket_2"]`) to `mod.properties.inputs.Socket_2.value`. Always go through `gn.set_input`/`get_input`, which handle both and coerce types (an int into a float socket otherwise errors).
- **Fill Curve defaults to Triangles.** Extruding a triangulated fill creates internal walls (non-manifold). Use `Mode="N-gons"`.
- **Merge By Distance at 1e-6 misses coincident points** at ~100s of units (float noise). Use 1e-4.
- **Mesh Boolean's default solver in 5.x mangled a simple pocket cut.** Set `solver="EXACT"` explicitly. `MANIFOLD` (5.x) is also clean and much faster when both operands are closed slabs. art-dealers-logo uses it for a tray pocket and for cutting about 650 traced letter points out of a box. Read the identifiers from `bl_rna` and fall back to `EXACT`.
- **Rebuilding a group must keep its interface.**
  - Until 2026-10-25, `gn.tree(..., reset=True)` also cleared the interface. That unlinked the group nodes other trees had wired to it: cerberus-mask's HeadProxy came out empty after every `blob_geo.py` edit, and the face cut silently did nothing. It also reset modifier inputs to the socket defaults: `Eye Height` dropped to 0.
  - Now `reset=True` clears only the nodes. `gn.input` / `gn.output` / `gn.panel` re-declare items by name; a changed socket type is replaced.
  - Call `gn.prune(t)` after declaring a rebuilt group's inputs to drop the ones the builder no longer makes.
  - Shared subgroups still build once per source: `if gn.current(t, __file__): return t` and `gn.stamp(t, __file__)` (`models/art-dealers-logo/builders/logo_geo.py`).
- **`gn.input` socket kinds are `kit.gn.SOCKET_TYPES` keys**: booleans are `"BOOL"`, not `"BOOLEAN"`.
- **Offset an outline by a margin** (there is no curve-offset node). For a convex result, the Minkowski sum with a circle works: Convex Hull → Instance on Points (Curve Circle, radius = margin) → Realize → Convex Hull. A planar hull comes out as one flat face that Extrude Mesh accepts. For a small inset or outset of any closed curve, Set Position with offset `normalize(tangent × ±Z) × d` works, provided every loop winds the same way relative to its filled side (traced contours do; see `image-logo-relief.md`).
- **Object Info in RELATIVE space** pins the result to the curve's world position. Moved hosts (variant copies) then lose their cuts. Patterns read curves in ORIGINAL space: edit the curve's points to reshape, and move the host to place.
- **Input names are params keys.** Keep them unique across patterns (hence the `Pocket` prefix), or scope a key to one object: `"Frame/Height"`.
- **Objects in a `hide_viewport` collection aren't evaluated**, so their evaluated mesh is empty in the live file (volume 0) even when drivers are correct. Check the display host instead, or let print-pack reveal the collection. Don't hide parts you need to measure over MCP.
- **Materials a builder recreates every time** (`materials.principled(name, colour)`) undo hand-picked colours on every rebuild. Create them only if missing (`bpy.data.materials.get(name) or ...`) and give them names a person would recognise ("Box Colour").

## Models
- art-dealers-logo (2026-10-21): traced logo curves → Fill Curve slabs, a box-minus-letters cut and an open tray (outer slab minus pocket), all GN on two hosts. Added the gotchas on the Manifold solver, shared subgroup resets and outline offsets.
- art-dealers-logo (2026-10-21, one-panel-and-stage): a single `Logo` display host with Size/Box/Lettering panels; the print bodies sit in the hidden Print collection and are driven from it (step 7).
