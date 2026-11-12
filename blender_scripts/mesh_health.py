"""Mesh health implementation shared by headless and live Bless checks."""

import bmesh
import bpy
from _common import model_objects


def report(collection: str = "Model") -> dict:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    objects = model_objects(collection=collection)
    result = {"unit_scale": bpy.context.scene.unit_settings.scale_length, "objects": []}
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        evaluated.to_mesh_clear()
        bm.transform(obj.matrix_world)
        bm.normal_update()
        xs, ys, zs = (
            zip(*(v.co[:] for v in bm.verts)) if bm.verts else ((0,), (0,), (0,))
        )
        flipped = sum(
            1
            for edge in bm.edges
            if len(edge.link_loops) == 2
            and edge.link_loops[0].vert == edge.link_loops[1].vert
        )
        scale = obj.matrix_world.to_scale()
        result["objects"].append(
            {
                "name": obj.name,
                "verts": len(bm.verts),
                "faces": len(bm.faces),
                "tris": sum(len(face.verts) - 2 for face in bm.faces),
                "ngons": sum(1 for face in bm.faces if len(face.verts) > 4),
                "non_manifold_edges": sum(
                    1 for edge in bm.edges if not edge.is_manifold
                ),
                "loose_verts": sum(1 for vert in bm.verts if not vert.link_edges),
                "loose_edges": sum(1 for edge in bm.edges if not edge.link_faces),
                "degenerate_faces": sum(
                    1 for face in bm.faces if face.calc_area() < 1e-10
                ),
                "flipped_edges": flipped,
                "unapplied_scale": any(abs(value - 1) > 1e-4 for value in obj.scale),
                "unapplied_rotation": any(
                    abs(value) > 1e-4 for value in obj.rotation_euler
                ),
                "negative_scale": any(value < 0 for value in scale),
                "modifiers": [modifier.type for modifier in obj.modifiers],
                "size": [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)],
                "bounds_min": [min(xs), min(ys), min(zs)],
            }
        )
        bm.free()
    return result
