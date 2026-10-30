---
name: wrap
description: Close a modeling session. Promotes logged steps into builders, confirms a clean rebuild, checks, exports and renders, finishes the session note, distills reusable techniques into workflows/, publishes a Speckle checkpoint, and offers a commit. Use when the user says "wrap", "wrap it up", "done for now", "finish the session", or invokes /wrap [model] [--done] [--turntable].
argument-hint: "[model] [--done] [--turntable]"
---

# Wrap: close a session

Arguments: $ARGUMENTS. With no model, use the one worked on in this conversation, else `uv run blend model latest`.

## 1. Lock in the model

1. Via MCP, assert `bpy.data.filepath` is `models/<m>/model.blend`.
2. **Promote steps.** Read this session's steps (`uv run blend history <m>`, plus the `log/NNN-*.py` files for this session). Fold the ones that define the model into `builders/NN_<part>.py`:
   - builders create GN groups and modifiers, and create Control defaults only if missing;
   - accepted param values go into `params.toml`;
   - explorations stay only in the log.
3. Run `build_all.py` over MCP, and `look` to confirm the rebuild matches. Check that Control edits survived.
4. Save.

## 2. Outputs

1. `just check <m>`. Fix issues, or record why they're acceptable.
2. `just export <m>`, then `just render <m>`. Read `render.png`. If the model has `[[views]]`, run `just views <m>`. If the model is on the Pages gallery (`models/<m>/web/model.glb` exists), also run `just site-export <m>` (`workflows/web-demo.md`).
3. `just turntable <m>` if `--turntable` is set or the user asks.
4. **Printable models** (a `print/` pack exists): run `uv run blend print-results <m>` (and `--pack <x>` for each extra pack with a `results.json`). Walk the **pending** recommendations with the user, one at a time:
   - **apply**: edit `model.toml` or the builder, rebuild, and add the id to `[print] feedback_applied` (`[print.<Coll>]` for an extra pack);
   - **decline**: add the id to `feedback_declined`, with a comment saying why.
   If any were applied (or the model changed since the last pack), re-pack: `just print-pack <m> [--collection X]`. Note stale-slice flags in the session note; slicing again is `/bambi:print`.

## 3. Record

1. Finish the session note: **Steps**, **Outcome** (check numbers, exports, compromises), **Next**.
2. Lessons worth keeping go into a workflow (next section) or into `brief.md` if model-specific. Be concrete: cause → fix.

## 4. Distill workflows

This step is the point of the repo. Follow `.context/writing-workflows.md`:
- update an existing doc before creating a new one;
- move generic helpers into `lib/kit` or `lib/patterns`;
- set `workflows = [...]` in `model.toml`;
- run `just workflows` to confirm none are flagged "no doc".

## 5. Checkpoint and close

1. Follow the `checkpoint` skill with `"<session summary>"` to publish a Speckle version (`.context/speckle-guide.md`). If Speckle isn't set up for this model yet, say so and skip.
2. If `--done` is set or the user says the model is finished: `just done <m>`.
3. Show a summary: the render, exports, check numbers, steps promoted, workflows touched, and the Speckle version.
4. Offer a commit, e.g. `feat(models): <m> <session slug>` plus `docs(workflows): ...`. Do **not** commit or push without the user's go-ahead.
