---
name: session
description: Work one short sitting on an existing model in the live Blender via blender-mcp. Loads only the model's brief, params, last session note and recent steps; models in small logged steps alongside the user. Use when the user says "work on <model>", "continue <model>", "next session", or invokes /session <model> [goal].
argument-hint: <model> [goal]
---

# Session: one sitting on a model

Arguments: $ARGUMENTS (model, then an optional goal). With no model, use `uv run blend model latest`.

Keep the context light. Read only what's listed in step 1. Pull in a workflow doc only when the step needs it.

## 1. Load (small)

1. Read `.context/blender-mcp-guide.md` and `.context/modeling-guide.md`.
2. For the model:
   - read `brief.md`, `params.toml` and the latest session note (`uv run blend session latest <m>`);
   - run `uv run blend history <m> --last 10`.
   Do **not** read old logs, builders or every note unless a step needs one.
3. If there's no goal, ask for one, offering the previous note's **Next** as the default.
4. Run `uv run blend session new <m> <slug> --goal "<goal>"`.

## 2. Connect

Follow **Connect** in `blender-mcp-guide.md`: if Blender isn't open, `just open <m>`; then `get_addon_status`, `get_scene_info`, and assert `bpy.data.filepath`.

## 3. Loop (per user prompt)

1. Re-read the state that matters. The user may have edited Control or modifier inputs. Mention any hand edits you notice.
2. Make one small, idempotent `execute_blender_code` step (see **Step size**). Prefer:
   - changing a GN input;
   - reshaping a Control curve on request;
   - adding a node or modifier.
   Baking geometry comes last.
3. `look` once (small `max_size`).
4. If the step changed the model, write the code to a scratch file and log it:
   `uv run blend step <m> <slug> --intent "<why>" --code-file <f> [--object X] [--param "Depth=60"]`.
5. Param changes the user accepts go back into `params.toml`.
6. To compare options, build a variant grid (`workflows/variant-grid-exploration.md`) and let the user pick.

Save (`bpy.ops.wm.save_mainfile()`) before any `just` command. When the user says "checkpoint", follow the `checkpoint` skill.

## 4. Close the sitting

Fill in the session note:
- **Steps:** the arc in 3-6 bullets, referencing step numbers.
- **Outcome:** state, dims and open issues.
- **Next:** the obvious next goal.

Save the file. Suggest wrapping (the `wrap` skill) to promote steps into builders, distill workflows, publish a checkpoint and commit.
