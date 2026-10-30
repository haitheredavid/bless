---
created: 2026-10-25
---
# cerberus-mask

## Intent
A wearable Halloween Cerberus costume piece, 3D-printed on the P1S, in two parts (layout chosen 2026-10-26):
- **Mask**: the center dog head, worn as a half mask with the mouth free and an elastic strap. The wearer looks out through its eye sockets.
- **Shoulder piece**: a hollow yoke worn on the shoulders with a harness. The two side heads rise from it on swan-arched necks.

The necks come up behind the center head's ears, so worn together the three heads close into one beast. The side heads are posed unevenly: left rears up and out, right lunges low and forward.

The format follows the three-headed raven mask (refs `IMG_3811.png`, `0778…png`, `8ee3…png`): center face plus two heads in profile. The head style follows the skeleton-dog toy (`51xSjBC4KNL.webp`): big dark sockets, tall pointed ears, toothy jaws. The etchings are the reference for heads joining through necks into one body. Overall size is about 580 × 430 × 400 mm.

Concept sketches (1 unit = 1 mm, origin at the pupils) are from before the layout choice:
- `sketches/front.svg`: half mask, skull, heads at the temples, front view.
- `sketches/top.svg`: spread and yaw, with seams for the bed.
- `sketches/side.svg`: 2×2 grid of profiles, half/full × skull/flesh.

## Requirements
- **Face fit:** the mask's inside is the Ref head proxy offset by `Face Clear` (6 mm: 3-5 mm foam plus clearance). Interpupillary distance is 63 mm.
- **Eyes:** see-through openings of at least 34 × 22 mm, centred on the pupils, framed by dark sockets of about 42 × 34 mm. A black hex-grille visor sits behind the openings, one lens per eye.
- **Field of view:** at least 45° outward, 60° down and 12° up per eye, measured with the side heads in place. Together that's ≥ 100° horizontal. `builders/checks.py` enforces it.
- **Breathing:** at least 400 mm² of open vent (nostrils into the hollow muzzle, plus the free mouth).
- **Wall:** 2.4 mm nominal, ≥ 1.6 mm everywhere (measured, not assumed). Sculpted relief ≥ 1.2 mm.
- **Bed:** every Print part ≤ 250 mm footprint (256 mm P1S bed).
- **Weight:** mask ≤ 200 g. Shoulder piece ≤ 600 g, hollow, carried on the shoulders by a harness.
- **Retention:** mask: two 25 × 4 mm strap slots at the temples for a 25 mm elastic band. Shoulder piece: harness slots (straps under the arms).
- **Joins:** glued loose tenons with a gable roof (as in witch-frame). Print a clearance coupon (0.10/0.15/0.20) first.
- **Full Mask only:** the lower jaw clears the wearer's chin by ≥ 15 mm with the mouth open.

## Plan
**Technique.** Organic forms as an SDF blob union in Geometry Nodes (`builders/blob_geo.py`):
- Bezier curves whose point radius is the thickness → SDF → fillet → mesh.
- The mask is an SDF shell around the face proxy.
- Cutters (eye openings, sockets, nostrils) are tagged curves subtracted after the blend.

**Parts** (`just build cerberus-mask` rebuilds them all; `builders/checks.py` enforces the requirements).
| Object | Group | Control | Builder |
|---|---|---|---|
| `Ref/HeadProxy` | baked from `GN_CerberusMask_Proxy` | `Ref/Ref_HeadProxy_Blobs` | `10_proxy.py` |
| `Work/Rig` | `GN_CerberusMask_Rig` (posed, tagged curves) | `Control/CTL_Head/*`, `Control/CTL_Collar` | `20_heads.py` |
| `Model/Mask` | `GN_CerberusMask_Mask` | Rig, HeadProxy | `20_heads.py` |
| `Model/Body` | `GN_CerberusMask_Body` (side heads, necks, yoke) | Rig | `20_heads.py` |
| `Model/Visor` | `GN_CerberusMask_Visor` | Rig, HeadProxy | `20_heads.py` |
| `Ref/Ref_Sketches` | SVG guides | `sketches/*.svg` | `30_guides.py` |
| `Print/*` | sections + tenons | Work seam planes | to come |

**Switches** (variant axes):
- `Full Mask`: adds the center lower jaw.
- `Side From Collar`: side heads on necks from the shoulder yoke (base) or at the temples (`temple`, `temple-asym` variants).
- `Flesh`: skull vs fleshed heads (not built).

**Sessions.**
1. Blockout, shell, cut-outs, visor, build pipeline. Done 2026-10-25/26.
2. Design-review rework (`sessions/2026-10-26-design-review.md`), in order:
   - eye sockets;
   - a dog-like front for the center muzzle;
   - head sizes (center biggest);
   - necks behind the center ears, with the right eye's view cleared;
   - finer mask resolution, with a measured wall;
   - ghost material for Ref;
   - hollow yoke with harness.
3. Strap slots, sections, joinery, coupon, print pack.
