# Project Context

## What This Repo Is

A general modeling and rendering environment for Blender, driven by an agent through blender-mcp while the user works alongside in the same Blender. Each **model** is long-lived and iterated across many short **sessions**. Techniques that work get distilled into `workflows/`. Downstream pipelines (e.g. bambi for 3D printing) build on its outputs.

Core value: the model stays **editable by hand** (parametric, Geometry Nodes driven by user-owned Control geometry), and the **iteration history is captured** (step log + Speckle versions), not just the final procedure.

## Architecture

```text
user <-> Blender (live)  <--MCP:9876-- agent (execute_blender_code, look)
              |  Speckle connector add-on --> app.speckle.systems (versions)
              v
         model.blend  --blender -b -P--> blender_scripts/*.py --> JSON results
              ^                                   ^
   lib/kit, lib/patterns (bpy helpers)      blend CLI (host, Python 3.13, typer)
```

- **Live:** the agent edits the open Blender via MCP in small steps; the user can edit the same scene.
- **Headless:** `blend` runs `blender -b model.blend -P script.py -- --result out.json` for check, export, render, views, turntable. It reads the file from disk, so save first.
- **History:** `blend step` appends to `models/<m>/log/`; `/checkpoint` publishes a version through the Speckle Blender connector.

## Ownership

| Area | Owns |
|------|------|
| `src/blend/` | Host CLI: model/session lifecycle, step log, headless orchestration, gallery. |
| `blender_scripts/` | Headless scripts run inside Blender. bpy/bmesh only. |
| `lib/kit/` | bpy helpers for builders and live MCP code (scene, mesh, materials, gn, params, control, ...). |
| `lib/patterns/` | Reusable Geometry Nodes pattern builders (one module each). |
| `models/<m>/` | One model: `.blend`, toml config, params, builders, log, sessions, exports, render. |
| `workflows/` | Technique docs distilled from sessions. |
| `assets/` | Studio scene and the patterns asset library. |
| `.claude/skills/` | `/model`, `/session`, `/checkpoint`, `/wrap`. They point at these guides. |
| `.omp/config.yml`, `.omp/commands/` | omp project settings (bambi skills from `../bambi`, print-start approval) and slash commands symlinked to the skills (`/new-model`, `/work`, `/checkpoint`, `/wrap`). |
| `AGENTS.md`, `.context/` | Agent context. |

## Durable Decisions

- **Geometry Nodes is the parametric core.** Builders create node groups and modifier stacks with exposed inputs; they do not bake. Applying a modifier is an explicit, logged "detach".
- **Collections ownership contract.** Control is user-owned and never cleared by builders; Model is procedural and rebuilt freely. See `modeling-guide.md`.
- **Long-lived models, light sessions.** `models/<m>/` persists; each session reads only the model brief, params, the last session note and recent log steps.
- **Two layers of history.** `log/` keeps every step's code verbatim (raw layers); `builders/` is the distilled rebuild. `/wrap` promotes steps into builders.
- **Variants in one model.** `params.toml [variants.<v>]` overrides, compared in one grid; one Speckle model per variant.
- **Speckle through the Blender connector.** The connector add-on owns login, publish and load. Checkpoints are explicit (and on session close), not per step.
- **AGENTS.md is canonical.** `CLAUDE.md` is a shim.
- **Units default to metres;** precise or printable work uses mm. Z up, model rests on z=0.
- Binaries go through Git LFS.
