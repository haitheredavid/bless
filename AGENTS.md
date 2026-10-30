# Agent Guide

## Project Context

blender-sessions is a general modeling and rendering environment. An agent drives a **live Blender** through blender-mcp while the user works alongside. Each model is long-lived in `models/<m>/`. It is iterated in short sessions, kept parametric (Geometry Nodes driven by user-owned Control geometry), and versioned to Speckle. Techniques that work are distilled into `workflows/`.

Durable context lives in `.context/` (conventions in `.context/README.md`):

- `.context/project-context.md` - purpose, architecture, ownership, durable decisions.
- `.context/blender-mcp-guide.md` - **read before any `mcp__blender__*` call**: connect, step size, look budget, co-editing, logging, recovery.
- `.context/modeling-guide.md` - units, collections ownership contract, Geometry Nodes and params conventions.
- `.context/engineering-guide.md` - commands, code areas, style, tests, LFS.
- `.context/speckle-guide.md` - Speckle Blender connector, checkpoints, version mapping.
- `.context/writing-workflows.md` - distilling techniques into `workflows/`.
- `.context/active/` - dated in-flight repo design docs; deleted when the work lands.

## Repo Shape

| Path | Owns |
|------|------|
| `src/blend/` | `blend` CLI (typer, host Python 3.13). |
| `blender_scripts/` | Headless scripts run inside Blender; bpy only; write JSON to `--result`. |
| `lib/kit/`, `lib/patterns/` | bpy helpers and GN pattern builders for builders and live MCP code. |
| `models/<m>/` | `model.blend`, `model.toml`, `params.toml`, `builders/`, `log/`, `sessions/`, `exports/`, `print/` (handoff pack), `web/` (Pages GLBs), `render.png`, `out/` (gitignored). |
| `models/_template/` | Copied by `blend model new`. |
| `workflows/` | Technique docs (`README.md` index, `_template.md`). |
| `assets/` | `studio.blend` render studio; `patterns.blend` GN asset library. |
| `refs/<m>/` | Third-party reference images (gitignored). |
| `docs/gallery/` | README gallery tiles, rewritten on every render. |
| `site/` | Pages gallery (Vite + R3F) over `models/*/web/*.glb`; see `workflows/web-demo.md`. |
| `.claude/skills/` | `/model`, `/session`, `/checkpoint`, `/wrap`. |
| `.omp/config.yml`, `.omp/commands/`, `.omp/lsp.json` | omp project settings: bambi skills from `../bambi`, print-start approval rule, Python LSP pinned to ty + ruff, `typescript-native` from `site/`. Slash commands symlinked to the `.claude/skills/` files. |

## Lifecycle

- `/model <idea>` - plan a new model, create `models/<m>/`, then start a session.
- `/session <m> [goal]` - a short sitting: load only the brief, params, last session note and recent steps; model live; log each step.
- `/checkpoint [msg]` - save, check, publish a Speckle version, record it in the log.
- `/wrap` - close the session: note, promote steps into builders, distill workflows, checkpoint, offer a commit.

In omp the same files are slash commands through symlinks in `.omp/commands/`: `/new-model`, `/work`, `/checkpoint`, `/wrap`. `/model` and `/session` are omp built-ins, so those two are renamed. `/skill:<name>` also works.

## Printing (bambi plugin)

3D prints go to bambi, enabled here as the `bambi@bambi` Claude Code plugin (`.claude/settings.json`): skills `/bambi:print` (check, plan, slice, send) and `/bambi:print-log` (log outcomes and coupon fits), and the `bambi` CLI on PATH. `just print-pack <m>` writes the pack; `bambi init models/<m>/print` then `/bambi:print models/<m>`; `just print-results <m>` reads what came back. See `workflows/print-handoff.md`. Ownership:

| File | Owner |
|------|-------|
| `model.toml`, `builders/`, `params.toml` | this repo |
| `print/**/manifest.json`, `parts.blend`, `stl/`, `README.md` | `blend print-pack` (bambi never edits them) |
| `print/**/session.toml`, `results.json`, `thumb.png`, `out/` | bambi (print-pack never deletes them) |

omp does not load Claude Code plugins enabled in `.claude/settings.json`. Instead `.omp/config.yml` points `skills.customDirectories` at `../bambi/src/bambi/skills` (`/skill:print`, `/skill:print-log`, ...), the CLI comes from `uv tool install --editable ../bambi`, and a `bash.patterns` prompt rule stands in for bambi's `guard_send` hook.

Recommendations in `results.json` are bambi's only channel back: apply or decline each, record its id in `[print] feedback_applied` / `feedback_declined`, re-pack. Never run `bambi printer send --start` without the user's go-ahead.

## Commands

Run `just` to list recipes. Key ones: `just ci`, `just fmt`, `just open <m>`, `just session <m> <slug>`, `just history <m>`, `just check|export|render|views|variants|animate|turntable <m>`, `just print-pack|print-results <m>`, `just wrap <m>`. The full CLI is `uv run blend --help`.

## Standards

- Z up, model on z=0, real-world size; metres by default, mm for precise work.
- Control is user-owned and never cleared by builders; Model is procedural. Do not apply modifiers without saying so.
- Small, idempotent MCP steps; `look` once per step; save before any `just` command.
- Find nodes by type, read enum identifiers, never hardcode `Socket_N`.
- Read the relevant `workflows/*.md` before modeling; update them at `/wrap`.

## Safety

- Never read or print `.env` values or Speckle credentials.
- Never quit Blender or save over another model's file. Ask before `generate_3d` (may cost credits).
- Commit only when asked; branch first if on `main`. Preserve unrelated dirty work.
