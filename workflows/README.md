# Workflows

Reusable Blender techniques distilled from sessions. Read the relevant ones before modeling (`/model` and `/session` do this). Write new ones or update existing ones when a session ends (`/wrap` does this; see `.context/writing-workflows.md`). Start each new doc from `_template.md`.

`just workflows` lists each doc with the models that use it, read from `workflows = [...]` in each `model.toml`.

| workflow | summary |
|---|---|
| [mcp-modeling-loop](mcp-modeling-loop.md) | The base loop: small MCP code steps, `look` often, persist in builders/, save before `just` |
| [ring-sweep-frame](ring-sweep-frame.md) | Watertight profiled frame/bezel from same-count rings bridged in a loop; freeform outline, parametric profile |
| [variant-grid-exploration](variant-grid-exploration.md) | Lay param variants side by side via a non-NN `explore.py`, `look`, and let the user pick |
| [print-fit-and-sectioning](print-fit-and-sectioning.md) | Rabbet stacks (glazing/art/board), turn-clip pockets, skin asserts, splitting for the printer bed |
| [photo-to-texture](photo-to-texture.md) | Perspective-crop a handheld photo of flat art to a real-size texture; show it in Solid and Material views |
| [render-views-and-sections](render-views-and-sections.md) | `blend views` named shots (upright, include, zoom), matching cameras, live red-capped section cut |
| [gn-patterns](gn-patterns.md) | Model as GN pattern modifiers on a host, driven by Control curves and params.toml; variants via `params.grid` / `blend variants` |
| [sketch-to-curve](sketch-to-curve.md) | Grease pencil sketch → simplified Bezier Control curve feeding GN patterns |
| [dimensions-and-annotation](dimensions-and-annotation.md) | Live GN dimension lines on Control anchors in Notes; annotated `views` |
| [animation](animation.md) | `kit.anim` param sweeps and exploded views, rendered with `blend animate` |
| [print-handoff](print-handoff.md) | `blend print-pack`: baked mm parts.blend + STLs + manifest for the printing agent (bambi) |
| [web-demo](web-demo.md) | `just site-export` + `blend site`: publish a model to the Pages gallery (R3F viewer, exploded print parts) |
| [image-logo-relief](image-logo-relief.md) | Logo image → traced Control curves (skimage) → two-colour GN relief/tray; stroke measurement, outline grow, sliver trim |
| [sdf-organic-blend](sdf-organic-blend.md) | Organic, printable forms from radius-weighted Control curves → SDF blend; tagged cutters, shells around a body proxy, grille inserts, requirement checks |
