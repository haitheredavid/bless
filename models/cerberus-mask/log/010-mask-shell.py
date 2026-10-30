# step 10: Center head becomes the wearable mask: SDF minus inside (Wall 2.4), face proxy + Face Clear 6, behind Mask Back 40; cutters tagged per head (eye sockets, nostrils)
# Cutters (CTL_Head_Cuts: eye sockets = wearer openings on the center head;
# CTL_Head_CutsSnout: nostrils) and the center head as a wearable shell: minus its inside
# (Wall), the face proxy + Face Clear, everything behind Mask Back, and the cutters.
import bpy

assert bpy.data.filepath.endswith("models/cerberus-mask/model.blend"), bpy.data.filepath
exec(open(bpy.path.abspath("//out/steps/_rebuild.py")).read(), {"__name__": "step"})  # noqa: S102, SIM115
