"""Force a supervised GUI Blender onto its BLESS_PORT add-on socket."""

import os

import bpy
from bpy.app.handlers import persistent

if bpy.app.background:
    raise RuntimeError(
        "Bless sessions require GUI Blender; background mode is unsupported"
    )

try:
    PORT = int(os.environ["BLESS_PORT"])
except (KeyError, ValueError) as exc:
    raise RuntimeError("BLESS_PORT must contain the supervised Blender port") from exc


def _configure_scenes() -> bool:
    if not hasattr(bpy.types.Scene, "blendermcp_port"):
        return False
    for scene in bpy.data.scenes:
        scene.blendermcp_port = PORT
        scene.blendermcp_auto_start_server = False
    return True


def _start_server():
    """Timer callback: wait for the add-on and a usable scene context."""
    if bpy.app.background:
        raise RuntimeError("Bless sessions require GUI Blender")
    if bpy.context.scene is None or not _configure_scenes():
        return 0.5

    server = getattr(bpy.types, "blendermcp_server", None)
    if server is not None and server.running and server.port != PORT:
        server.stop()
        del bpy.types.blendermcp_server
        server = None
    if server is not None and server.running and server.port == PORT:
        bpy.context.scene.blendermcp_server_running = True
        return None

    result = bpy.ops.blendermcp.start_server()
    if "FINISHED" not in result:
        return 0.5
    return None


def _schedule() -> None:
    if not bpy.app.timers.is_registered(_start_server):
        bpy.app.timers.register(_start_server, first_interval=0.1, persistent=True)


@persistent
def _bless_load_post(_unused) -> None:
    _configure_scenes()
    _schedule()


if _bless_load_post not in bpy.app.handlers.load_post:
    bpy.app.handlers.load_post.append(_bless_load_post)
_configure_scenes()
_schedule()
