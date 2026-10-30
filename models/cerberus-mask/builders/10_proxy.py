# Ref head proxy (generic adult bust, pupils at Eye Height, bust on z=0) that the mask is
# hollowed around and the visor sits on. Built from the Ref/Ref_HeadProxy_Blobs curves
# (blob_geo.PROXY; created once, user-editable) and BAKED to a plain mesh: the blend takes
# ~13 s, and the mask/visor read HeadProxy on every update. Re-baked only when the blob
# curves change (hash in HeadProxy["blob_hash"]). Ref is user-owned: HeadProxy's mesh data
# is replaced, the object is never deleted.
import hashlib
import importlib
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).parent))
import blob_geo
from kit import gn, scene

importlib.reload(blob_geo)

coll = blob_geo.proxy_controls()


def _blob_hash(c) -> str:
    h = hashlib.sha1()
    for o in sorted(c.all_objects, key=lambda o: o.name):
        h.update(o.name.encode())
        h.update(repr(tuple(round(v, 3) for v in o.matrix_world.translation)).encode())
        for sp in o.data.splines:
            for bp in sp.bezier_points:
                h.update(
                    repr(
                        (tuple(round(v, 3) for v in bp.co), round(bp.radius, 3))
                    ).encode()
                )
    return h.hexdigest()[:12]


digest = _blob_hash(coll)
proxy = bpy.data.objects.get("HeadProxy")
if proxy is None or proxy.get("blob_hash") != digest or not proxy.data.polygons:
    tmp = gn.host("_HeadProxy_Bake", scene.work())
    gn.modifier(tmp, blob_geo.proxy_group(coll))
    bpy.context.view_layer.update()
    mesh = bpy.data.meshes.new_from_object(
        tmp.evaluated_get(bpy.context.evaluated_depsgraph_get())
    )
    bpy.data.objects.remove(tmp, do_unlink=True)
    mesh.name = "HeadProxy"
    if proxy is None:
        proxy = bpy.data.objects.new("HeadProxy", mesh)
        scene.link(proxy, scene.collection(scene.REF))
    else:
        old = proxy.data
        proxy.data = mesh
        proxy.modifiers.clear()
        if old.users == 0:
            bpy.data.meshes.remove(old)
    proxy["blob_hash"] = digest
    print(f"10_proxy: baked HeadProxy ({len(mesh.polygons)} faces)")

# Ghost material: the bust is context, not the subject (design review: it was the biggest
# shape in every render). Created once, so a hand-picked look survives rebuilds.
ghost = bpy.data.materials.get("Ref Ghost")
if ghost is None:
    ghost = bpy.data.materials.new("Ref Ghost")
    ghost.use_nodes = True
    bsdf = next(n for n in ghost.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.55, 0.62, 0.75, 1.0)
    bsdf.inputs["Alpha"].default_value = 0.25
    if hasattr(ghost, "surface_render_method"):
        ghost.surface_render_method = "BLENDED"
    ghost.diffuse_color = (0.55, 0.62, 0.75, 0.25)
if proxy.data.materials[:] != [ghost]:
    proxy.data.materials.clear()
    proxy.data.materials.append(ghost)
assert proxy.data.polygons, "HeadProxy is empty"
