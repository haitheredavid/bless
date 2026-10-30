---
name: model
description: Start a new Blender model. Plans it first (intent, references, scale, parts as Geometry Nodes patterns driven by Control inputs, params and variants, which workflows apply), then on approval creates models/<name>/ and hands off to /session for the first build. Use when the user says "make a <thing>", "model a <thing>", "new model", or invokes /model <idea>.
argument-hint: <what to model>
---

# Model: plan a new model

The user wants to model: $ARGUMENTS

Plan first (no files touched), then create the model once the plan is approved. Building happens in `/session`. That keeps this context small.

## Stage 1: Plan

1. Enter plan mode if the harness has one (Claude Code: `EnterPlanMode`); either way, touch no files until the plan is approved.
2. Read `.context/modeling-guide.md`. Run `uv run blend model ls` and `just workflows`. Read the `workflows/*.md` that might apply, and the `brief.md` of any similar model.
3. Ask **one** round of questions (Claude Code: `AskUserQuestion`; omp: `ask`), only for what the request leaves open and what changes the build:
   - **Purpose:** still render, animation, game asset, 3D print (downstream pipeline), kit part.
   - **Style and detail:** realistic or stylized, hard-surface or organic.
   - **Scale and units:** real-world size; `--unit mm` for precise or printable work.
   - If the purpose is **3D print**: use `--unit mm`, plan a **Print** collection (parts split for the 256 mm bed, joinery cut) and the `[print]` table (material, `[[print.part]]` supports/orientation intent, coupons for fits; `workflows/print-handoff.md`). Readiness checks and slicing are bambi's `print` skill, on the pack from `just print-pack`.
   - **References:** images in `refs/<slug>/` (gitignored), a sketch, or an asset (`search_assets`; `generate_3d` costs credits).
   - **What to explore:** which params the user wants as variants.
4. Write the plan:
   - **Name:** a kebab-case slug, which becomes `models/<slug>/`.
   - **Intent:** one or two sentences for `model.toml`.
   - **Requirements:** hard constraints as numbers.
   - **Parts:** for each part:
     - the Model object name;
     - its **Control inputs** (`CTL_*` curves and empties the user can reshape);
     - the GN pattern or technique (`lib/patterns/*`, `workflows/*.md`);
     - its exposed params with defaults;
     - the builder file (`builders/NN_<part>.py`).
   - **Params and variants:** the `[base]` table and the first `[variants.*]` to compare.
   - **First session goal:** what the first `/session` should reach (usually blockout + variant grid).
   - **Verification:** `just check` expectations, plus `[[views]]` worth defining.
5. Present the plan and wait for approval (Claude Code: `ExitPlanMode`).

## Stage 2: Create (after approval)

1. Run `just new <slug>` (add `--unit mm|cm`). This creates `models/<slug>/` and opens `model.blend` with the Model/Control/Work/Notes/Ref collections.
2. Fill in `model.toml` (`intent`, `tags`, `workflows`, `[export]`, `[[views]]`), `brief.md` (Intent, Requirements, Plan) and `params.toml` (`[base]`, variants).
3. Continue straight into the `session` skill with `<slug> <first-goal>`.
