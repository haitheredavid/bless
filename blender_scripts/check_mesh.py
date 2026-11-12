"""Mesh health checks on the Model collection (or --collection), written as JSON.

Usage: blender -b model.blend -P check_mesh.py -- [--collection Print] --result r.json

Per object: verts/faces/tris, n-gons, non-manifold edges, loose verts/edges, degenerate
faces, inconsistent normals, unapplied scale/rotation, world-space size.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import parse, write_result
from mesh_health import report

parser = argparse.ArgumentParser()
parser.add_argument("--collection", default="")
opts = parse(parser)

write_result(opts.result, report(opts.collection))
