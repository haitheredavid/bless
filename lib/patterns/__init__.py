"""patterns: reusable Geometry Nodes groups, one module per pattern.

Each module has NAME (the node group, GN_<Pattern>), build(reset=False) -> node group
(idempotent: returns the existing group unless reset), and apply(obj, **inputs) ->
modifier. Patterns read Control objects through Object inputs and expose every tunable as
a named group input, so the user can drive them from the modifier panel. Control curves
are read in ORIGINAL space: edit their points (not their object transform) to reshape;
move the host object to place the result.

Chain patterns as a modifier stack on one host object (e.g. profile_sweep, then
pocket_cut). `blend patterns-lib` writes them all to assets/patterns.blend as assets.
"""

from patterns import (
    frame_loft,
    joints,
    outline_extrude,
    pocket_cut,
    profile_sweep,
    section_piece,
)

ALL = (
    profile_sweep,
    outline_extrude,
    pocket_cut,
    frame_loft,
    section_piece,
    *joints.ALL,
)


def build_all(reset: bool = False) -> list:
    return [p.build(reset) for p in ALL]
