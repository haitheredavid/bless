"""patterns.joints: printable joinery as Geometry Nodes groups.

Every joint group (GN_Joint_<Kind>) shares one contract (see _common.joint_inputs):

- Part: 0 = A, 1 = B, 2 = the loose part alone (key, pin, tenon). The same group on
  both mates keeps their geometry in one place.
- Clearance: gap per mating face. Only B and sockets carry it; A and loose parts are
  nominal, so one A tests several B's in a clearance sweep. Negative = interference.
- Joint Origin / Joint Rotation: host-local joint frame. Mating axis +X, joint face at
  x = 0, A on -x, B on +x, up +Z. The joint spans the host's z extent in that frame.
- Joint Chamfer: 45 deg chamfer on male edges, flare on socket mouths (FDM: elephant's
  foot, lead-in).

GN_JointBar is the specimen bar (A on -x, B on +x, engraved label); GN_JointExplode
pulls an assembled display pair apart. Stack them on one host:
JointBar -> Joint_<Kind> -> JointExplode, with the same Part on each.
"""

from patterns.joints import butterfly, dovetail, explode, joint_bar

ALL = (joint_bar, dovetail, butterfly, explode)
