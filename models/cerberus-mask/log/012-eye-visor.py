# step 12: Option B: printed hex-grille visor glued inside the mask behind the eye openings (Visor object, Output Visor); 109x24x47 mm, 2.9 cm3, manifold; blob group keeps its interface on rebuild
# Eye visor (option B): Visor object = GN_CerberusMask_Heads with Output Visor on. A 1.2 mm
# plate on the mask's inside (face proxy + Face Clear), trimmed to the vision cutters + 8 mm
# glue margin (mesh boolean), with a hex grille (3.0 holes, 0.9 bars), at 0.5 mm voxels on
# the eye region only. GN_SDFBlob now keeps its interface on rebuild (proxy no longer
# unlinks after blob_geo.py edits).
import bpy

assert bpy.data.filepath.endswith("models/cerberus-mask/model.blend"), bpy.data.filepath
exec(open(bpy.path.abspath("//out/steps/_rebuild.py")).read(), {"__name__": "step"})  # noqa: S102, SIM115
