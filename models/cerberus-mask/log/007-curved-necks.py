# step 7: Collar-asym promoted to [base] (temple variants keep the old setup); necks are quadratic Beziers with Neck Curve (swan arch) and Neck Taper
# Live rebuild for this session: heads tree, then the proxy (relinks GN_SDFBlob), then
# params [base] (plus an optional variant). Prints dims / islands / manifold for Heads.
import bmesh
import bpy

assert bpy.data.filepath.endswith("models/cerberus-mask/model.blend"), bpy.data.filepath
D = bpy.path.abspath("//out/steps/")
exec(open(D + "02_heads.py").read(), {"__name__": "step"})  # noqa: S102, SIM115
exec(open(D + "01_proxy.py").read(), {"__name__": "step"})  # noqa: S102, SIM115
from kit import params

params.apply("base")
if globals().get("VARIANT"):
    params.apply(params.load(VARIANT))  # noqa: F821
bpy.context.view_layer.update()
ev = bpy.data.objects["Heads"].evaluated_get(bpy.context.evaluated_depsgraph_get())
bm = bmesh.new()
bm.from_mesh(ev.data)
vs = [v.co for v in ev.data.vertices]
seen, islands = set(), 0
for f in bm.faces:
    if f.index in seen:
        continue
    islands += 1
    stack = [f]
    while stack:
        x = stack.pop()
        if x.index in seen:
            continue
        seen.add(x.index)
        stack += [g for e in x.edges for g in e.link_faces if g.index not in seen]
print({"dims": [round(max(v[i] for v in vs) - min(v[i] for v in vs)) for i in range(3)],
       "islands": islands, "nonmanifold": sum(1 for e in bm.edges if not e.is_manifold),
       "vol_cm3": round(bm.calc_volume() / 1000)})  # fmt: skip
