# 2026-10-17 dt-bk-foundation

## Goal
GN_JointBar + joint contract (Part/Clearance/Origin/Rotation), sliding dovetail (DT) and butterfly key (BK), display board row 1, Print_Interlock pack with DT/BK sweeps

## Steps
- (1) Joint library `lib/patterns/joints/`: `_common` helpers (trap-box hulls with perpendicular clearance offset, flares, A/B/Loose switch, joint frame), `GN_JointBar` (chamfered bar, engraved front label), `GN_Joint_Dovetail` (tail on A; socket + clearance, flared mouths on B). Registered in `patterns.ALL`; `blend patterns-lib` rebuilt `assets/patterns.blend`.
- (2) `GN_Joint_Butterfly`: chamfered bowtie key (Loose) and clearance pockets in both bars, key one layer below flush.
- (3) Promoted to builders: `catalog.py` (DT, BK: fit, sweep, kind, checks), `10_board.py` (assembled row on `CTL_Board`), `20_print.py` (`Print_Interlock` sweep parts + `joints` JSON). Added `GN_JointExplode`. `build_all` clean, no unused params.
- Gotchas: Extrude Mesh's `Individual` defaults to on (each fill triangle got its own walls, and N-gons fill can't hold a glyph counter): use Triangles + Individual off. Rebuilding a group (`gn.tree(reset=True)` clears the interface) leaves zeros in existing modifiers' inputs: recreate hosts after a pattern edit (build_all does).

## Outcome
- Model: DT and BK assembled at their `fit` (0.20 / 0.10). `just check` clean.
- `Print_Interlock`: DT_A + DT_B15/20/30, BK_A/B05/10/15 + BK_K. `--strict` clean; raycast gaps 0.05 / 0.10 / 0.15 / 0.20 / 0.30 exactly as labelled (perpendicular to the flanks); key 12.8-17.8 on a 12.8 floor.
- Pack `print/print_interlock/`: 11 parts, 76.4 cm³, 1 plate, all watertight, supports none. Coupons `DT` and `BK` declared in model.toml.
- Open: print-spec has no `dovetail` joint kind (6 warnings). Extend bambi's spec, or map to the nearest kind; decide before Session 2 adds finger / puzzle / half-lap.

## Next
Print the Interlock pack (`bambi init models/joinery-sampler/print/print_interlock`, then `/skill:print`), and in parallel Session 2: tapered dovetail (TD), finger/box (FJ), puzzle tab (PZ, `CTL_Puzzle_Profile`), half-lap (HL).
