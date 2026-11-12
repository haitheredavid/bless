# Engineering Guide

## Commands

`just` wraps the common commands; run `just` to list them. The CLI is `uv run blend ...`.

- `just ci` - ruff check + format check + pytest.
- `just fmt` - auto-fix lint and format.
- `just open <m>` - open a model's `.blend` (MCP bridge auto-starts).
- `just supervisor` - supervise requested GUI Blender sessions; SIGINT/SIGTERM stops the supervisor but intentionally leaves healthy Blender processes running.
- `just status` - read `.bless/sessions` without requiring the supervisor or Herdr.
- `just check|export|render|views|turntable <m>` - headless runs against the saved file.
- `just wrap <m>` - check, export, render.
- `just site-export <m>`, `just site-dev`, `just site-build` - the Pages gallery (see `workflows/web-demo.md`).

## Code areas

- **`src/blend/`**: host-side Python 3.13, typer CLI. It never imports bpy. It shells out to Blender through `blend.blender`.
- **Bless runtime**: `blend.sessions` owns atomic `.bless/` records and ports, `blend.supervisor` owns GUI Blender processes, and `blend.commands` talks directly to each add-on socket. The separate `bless` console script leaves existing `blend` behavior unchanged.
- **Prompt graph**: `models/<m>/log/prompts.jsonl` is committed source truth imported from disposable omp transcripts. `models/<m>/graph.json` is also committed: it is a deterministic, strict explorer artifact that works without access to those transcripts. `blend.graph` owns import, corrections, derivation, camera conversion and replay planning.
- **`blender_scripts/`**: runs inside Blender as `blender -b file.blend -P script.py -- --result out.json ...`.
  - bpy/bmesh only; never import `blend`. They may import `lib/kit` and `lib/patterns` (bpy-only) by putting `lib/` on `sys.path`.
  - Each script takes `--result` and writes JSON there. `_common.py` holds the shared arg and collection helpers.
- **`lib/kit/`, `lib/patterns/`**: bpy helpers imported by builders and by live MCP code once `lib/` is on `sys.path`. Keep functions small, named by what they build, and idempotent where possible.
- **`lib/cmdline/`**: Blender side of `blend repl` (`src/blend/repl.py`, `src/blend/bridge.py`): command functions and the persistent-namespace runner, called through the blender-mcp socket. Host-side parsing is tested in `tests/test_repl.py`.
- **`site/`**: the Pages gallery (Vite + React + TypeScript + React-Three-Fiber, pnpm). It reads `public/models.json` and the model files that `blend site` (`src/blend/site.py`) copies in; both are gitignored. `.github/workflows/pages.yml` builds and deploys it with base `/<repo name>/`.
- **Builders** (`models/<m>/builders/`): model-specific; promote generic helpers into `lib/`.

## Python style

- ruff for lint and format. Type hints on public functions.
- ty for type checking (`uv run ty check`, not part of `just ci`). Dev group carries `fake-bpy-module-5.2` stubs, and `[tool.ty.environment] extra-paths` puts `lib/` and `blender_scripts/` on the import path.
- omp language servers: ty + ruff (from `.venv`), marksman, and the built-in `typescript-native` for `site/`. `.omp/lsp.json` disables pyright, basedpyright and pylsp so ty is the only Python type server, and runs `typescript-native` from `site/node_modules/.bin/tsc` (TypeScript 7, `pnpm install` in `site/` first), rooted on `site/tsconfig.json`.
- `@dataclass` for internal structures; `pydantic-settings` for config (`blend.config`).
- Validate config early and raise a `ValueError` naming the toml key (see `Model.views()`).
- Edit toml in place with `set_field` so comments survive; parse the result before writing.

## Tests

- pytest in `tests/`. Cover config parsing, path logic, the step log, and anything host-side.
- Tests never launch Blender. Blender-side behavior is verified live through MCP or by running the headless command by hand.

## Prompt graph heuristics

- A transcript prompt owns steps timestamped after it and before the next real user prompt in that transcript; explicit model/session mentions disambiguate overlapping transcripts.
- A prompt with owned code or parameter steps is `model`. Otherwise scene vocabulary (camera, view, render, display, lighting) makes it `scene`; modeling vocabulary makes it a queued model prompt. Unacted chat with neither vocabulary nor steps is excluded, including operational requests such as commit, branch, CI, printing or deployment.
- Each step not owned by a transcript prompt becomes its own `step-log` prompt, preserving every historical model version. A later transcript claim replaces an untouched fallback; agent/user-tagged fallbacks are retained with a warning.
- Model-node size is `2 * unique objects + 1.5 * changed params + min(code bytes / 1000, 5)`, normalized to the largest score in that model.
- Consecutive prompts in one session get a link using their leading connective phrase, or `next`. Scene references follow the latest prior applied model prompt unless pinned explicitly or by naming a version/step.
- Snapshots are linked only when an existing PNG/JPEG is within 24 hours of the prompt (same session runtime snapshots first, then model outputs/render); stored paths are relative to the Bless root.

## Binaries and LFS

- `*.blend`, images, `*.glb|fbx|obj|stl|3mf`, video and gif live in Git LFS (`.gitattributes`). Fresh clones need `git lfs install`.
- `models/*/out/` and `*.blend1` are gitignored.

## Search scope

Exclude `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `models/*/out/`, and binaries when grepping.

## Safety

- Never read or print `.env` values or Speckle credentials.
- Commit only when the user asks. Branch first if on `main`.
- Preserve unrelated dirty work; never revert files you did not change.
