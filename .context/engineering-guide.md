# Engineering Guide

## Commands

`just` wraps the common commands; run `just` to list them. The CLI is `uv run blend ...`.

- `just ci` - ruff check + format check + pytest.
- `just fmt` - auto-fix lint and format.
- `just open <m>` - open a model's `.blend` (MCP bridge auto-starts).
- `just build <m> [--variant preview]` - rebuild headless from `builders/` and save model.blend; no MCP timeout. It fails on builder errors, GN inputs without a params key, and the model's `builders/checks.py`. Revert an open Blender afterwards (File > Revert).
- `just check|export|render|views|turntable <m>` - headless runs against the saved file.
- `just wrap <m>` - check, export, render.
- `just site-export <m>`, `just site-dev`, `just site-build` - the Pages gallery (see `workflows/web-demo.md`).

## Code areas

- **`src/blend/`**: host-side Python 3.13, typer CLI. It never imports bpy. It shells out to Blender through `blend.blender`.
- **`blender_scripts/`**: runs inside Blender as `blender -b file.blend -P script.py -- --result out.json ...`.
  - bpy/bmesh only; never import `blend`. They may import `lib/kit` and `lib/patterns` (bpy-only) by putting `lib/` on `sys.path`.
  - Each script takes `--result` and writes JSON there. `_common.py` holds the shared arg and collection helpers.
- **`lib/kit/`, `lib/patterns/`**: bpy helpers imported by builders and by live MCP code once `lib/` is on `sys.path`. Keep functions small, named by what they build, and idempotent where possible.
- **`lib/cmdline/`**: Blender side of `blend repl` (`src/blend/repl.py`, `src/blend/bridge.py`): command functions and the persistent-namespace runner, called through the blender-mcp socket. Host-side parsing is tested in `tests/test_repl.py`.
- **`site/`**: the Pages gallery (Vite + React + TypeScript + React-Three-Fiber, pnpm). It reads `public/models.json` and the model files that `blend site` (`src/blend/site.py`) copies in; both are gitignored. `.github/workflows/pages.yml` builds and deploys it with base `/<repo name>/`.
- **Builders** (`models/<m>/builders/`): model-specific; promote generic helpers into `lib/`.

## Python style

- ruff for lint and format. Type hints on public functions.
- `@dataclass` for internal structures; `pydantic-settings` for config (`blend.config`).
- Validate config early and raise a `ValueError` naming the toml key (see `Model.views()`).
- Edit toml in place with `set_field` so comments survive; parse the result before writing.

## Tests

- pytest in `tests/`. Cover config parsing, path logic, the step log, and anything host-side.
- Tests never launch Blender. Blender-side behavior is verified live through MCP or by running the headless command by hand.

## Binaries and LFS

- `*.blend`, images, `*.glb|fbx|obj|stl|3mf`, video and gif live in Git LFS (`.gitattributes`). Fresh clones need `git lfs install`.
- `models/*/out/` and `*.blend1` are gitignored.

## Search scope

Exclude `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `models/*/out/`, and binaries when grepping.

## Safety

- Never read or print `.env` values or Speckle credentials.
- Commit only when the user asks. Branch first if on `main`.
- Preserve unrelated dirty work; never revert files you did not change.
