# Variant-grid exploration

Lay out parameter variants of a parametric builder side by side, look at them in one or two `look` calls, and let the user pick. Use it when the brief says "experiment with X" or the right proportions aren't known yet.

## When to use
- The model is built by a function of params (e.g. `build_frame(p)`), and there are 2–3 axes worth comparing (depth × profile, sag × tip shape).
- The user should choose. Show them a grid, not a description.

## Steps
**GN models** (`workflows/gn-patterns.md`): put the options in `params.toml [variants.*]`. Then either:
- **live**, run `from kit import params; params.grid()`, `look`, then `params.clear_grid()`; or
- **rendered**, run `uv run blend variants <m> [--view NAME]`, which writes `out/variants.png`.

The steps below are for bmesh builders, which have no modifier inputs.

1. **Keep the geometry in a module** (`builders/<part>_geo.py`) with `params(**overrides)`, `validate(p)` and `build_bmesh(p)`. The NN builder and the explore script both import it.
2. **Write `builders/explore.py`** with no NN_ prefix, so `build_all` skips it. Its `grid(rows, base)` builds each variant into an `Explore` collection, spaced by the model size plus a gap. It hides Model while exploring; `clear()` restores it.
3. **Validate every variant** and print `INVALID <reason>` instead of building the bad ones. Constraint failures show up in the log, not in a render.
4. **Look with two views:**
   - `look(mode="angles", views=["top"])` for outlines;
   - a low 3/4 view such as `[0.35, -1, 0.55]` for depth and profile.
   - Use a light grey explore material: dark materials read as silhouettes in solid shading.
5. **Save the screenshots** to `out/explore-<axis>.png`, ask the user (Claude Code: `AskUserQuestion`; omp: `ask`) with rows and columns described in the question, write the pick into the NN builder's params with a comment pointing at the screenshots, then `clear()`.

## bpy
```python
g = {"__name__": "explore", "__file__": bpy.path.abspath("//builders/explore.py")}
exec(open(g["__file__"]).read(), g)
rows = [[{"sag": s, "k": k} for s in (8, 12, 15)] for k in (1.3, 0.5)]
g["grid"](rows, base={"depth": 40})
# ... look ...
g["clear"]()
```
Reference implementation: `models/witch-frame/builders/explore.py`.

## Gotchas
- **Grid order:** row 0 sits at y=0, and later rows go to −y. From a front 3/4 view the *last* row is nearest the camera, so say which row is which when asking.
- **Keep variants at real size.** Scaling them down to fit hides wall-thickness issues.
- **Run `build_all` after `clear()`.** The grid shares materials and may leave the Model hidden.

## Models
- witch-frame (2026-10-10): edge grid (sag × tip sharpness, plus wobble) and depth grid (25/40/55 × linear/cove/convex); the user picked from the screenshots.
