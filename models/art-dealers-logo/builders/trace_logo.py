"""Trace refs/art-dealers-logo/logo.png into builders/logo_trace.json (host-side, not run by build_all).

    uv run --with pillow --with numpy --with scikit-image python models/art-dealers-logo/builders/trace_logo.py

Output, in mm with the logo centred on the origin and LOGO_WIDTH wide (Y up):
  art, galeria      light letter outlines (outer contours and counters; Fill Curve nests them)
  dealers_text      dark Dealers letters inside the box, extended EDGE px past the box where they touch it;
                    light box slivers thinner than MIN_STROKE are added to them so the cut removes them
  dealers_box       [xmin, ymin, xmax, ymax] of the light box
10_control.py turns each group into a CTL_* curve if missing; Control is then the user's.
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image
from skimage import filters, measure, morphology, transform

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "refs/art-dealers-logo/logo.png"
OUT = Path(__file__).with_name("logo_trace.json")

LOGO_WIDTH = 150.0  # mm; the GN "Logo Width" input rescales from this
UP = 4  # upsample factor before contouring
SIGMA = 1.2  # blur in upsampled px; rounds off the JPEG staircase
TOL = 0.6  # polygon simplify tolerance, upsampled px
LEVEL = 0.5  # threshold on the normalised image
MIN_AREA = 25.0  # px²; Dealers loops smaller than this are box-corner specks (smallest real counter ~480 px²)
MIN_STROKE = 0.8  # mm; light box between Dealers letters thinner than this is cut away (two 0.4 mm lines)
SLIVER_MIN_AREA = 0.05  # mm²; smaller "slivers" are just the opening rounding a corner
BOX = (
    386,
    189,
    759,
    288,
)  # light Dealers box, px [x0, y0, x1, y1) (measured from column/row profiles)
EDGE = 3  # px the Dealers letters are pushed past the box edge, so the boolean cuts cleanly
ART_MAX_X = 380  # "Art" is left of the box
GALERIA_MIN_Y = 295  # "GALERIA" is below the box


def contours(
    img: np.ndarray,
    origin: tuple[float, float],
    min_area: float = 0.0,
    sliver_r: float = 0.0,
    sliver_min: float = 0.0,
) -> list[np.ndarray]:
    """Closed contours of a 0..1 image at LEVEL, back in source px (x, y); loops under min_area px² dropped.
    sliver_r > 0 (upsampled px): `img` is the Dealers crop padded by EDGE. Light parts inside the box
    narrower than 2 * sliver_r (and bigger than sliver_min upsampled px²) are made dark, and carried
    out through the EDGE band so the boolean cuts them cleanly at the box edge."""
    big = transform.rescale(img, UP, order=3)
    big = filters.gaussian(big, SIGMA)
    if sliver_r > 0:
        r, e = int(np.ceil(sliver_r)), EDGE * UP
        inside = np.zeros(big.shape, bool)
        inside[e:-e, e:-e] = True
        light = (
            big < LEVEL
        ) & inside  # beyond the box edge there is no box: slivers along it are thin
        kept = morphology.binary_opening(np.pad(light, r + 1), morphology.disk(r))[
            r + 1 : -r - 1, r + 1 : -r - 1
        ]
        thin = morphology.remove_small_objects(light & ~kept, int(sliver_min))
        thin |= morphology.binary_dilation(thin, morphology.disk(e + 2)) & ~inside
        big = np.where(thin, 1.0, big)
        mm2 = (thin & inside).sum() * (MIN_STROKE / 2 / sliver_r) ** 2
        print(
            f"slivers cut: {measure.label(thin & inside).max()} regions, {mm2:.2f} mm²"
        )
    big = np.pad(big, 1)  # every contour closes inside the array
    out = []
    for c in measure.find_contours(big, LEVEL):
        c = measure.approximate_polygon(c, TOL)
        if len(c) < 4:
            continue
        rc = (c - 1 + 0.5) / UP - 0.5  # upsampled px centre -> source px centre
        xy = np.stack([rc[:, 1] + origin[0], rc[:, 0] + origin[1]], 1)
        x, y = xy[:, 0], xy[:, 1]
        if abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2 < min_area:
            continue
        out.append(xy[:-1] if np.allclose(xy[0], xy[-1]) else xy)
    return out


def main() -> None:
    a = np.asarray(Image.open(SRC).convert("L")).astype(float) / 255.0
    light = (a - a.min()) / (a.max() - a.min())
    h, w = light.shape

    yy, xx = np.mgrid[0:h, 0:w]
    in_box = (xx >= BOX[0]) & (xx < BOX[2]) & (yy >= BOX[1]) & (yy < BOX[3])
    art = np.where((xx < ART_MAX_X) & (yy < GALERIA_MIN_Y) & ~in_box, light, 0.0)
    galeria = np.where(yy >= GALERIA_MIN_Y, light, 0.0)
    dark = 1.0 - light[BOX[1] : BOX[3], BOX[0] : BOX[2]]
    dark = np.pad(dark, EDGE, mode="edge")

    groups = {
        "art": contours(art, (0, 0)),
        "galeria": contours(galeria, (0, 0)),
    }
    # logo bounds: Art and GALERIA plus the box (the Dealers cutters overshoot the box on purpose)
    pts = np.concatenate(groups["art"] + groups["galeria"])
    lx0, lx1 = pts[:, 0].min(), BOX[2] - 0.5
    ly0, ly1 = min(pts[:, 1].min(), BOX[1] - 0.5), pts[:, 1].max()
    s = LOGO_WIDTH / (lx1 - lx0)  # mm per source px
    cx, cy = (lx0 + lx1) / 2, (ly0 + ly1) / 2
    up_px = s / UP  # mm per upsampled px
    groups["dealers_text"] = contours(
        dark,
        (BOX[0] - EDGE, BOX[1] - EDGE),
        MIN_AREA,
        sliver_r=MIN_STROKE / 2 / up_px,
        sliver_min=SLIVER_MIN_AREA / up_px**2,
    )

    def mm(xy: np.ndarray) -> list[list[float]]:
        return np.round(
            np.stack([(xy[:, 0] - cx) * s, -(xy[:, 1] - cy) * s], 1), 4
        ).tolist()

    data = {
        "source": str(SRC.relative_to(ROOT)),
        "mm_per_px": s,
        "logo_width": LOGO_WIDTH,
        **{k: [mm(c) for c in v] for k, v in groups.items()},
        "dealers_box": [
            round((BOX[0] - 0.5 - cx) * s, 4),
            round(-(BOX[3] - 0.5 - cy) * s, 4),
            round((BOX[2] - 0.5 - cx) * s, 4),
            round(-(BOX[1] - 0.5 - cy) * s, 4),
        ],
    }
    OUT.write_text(json.dumps(data))
    size = (round((lx1 - lx0) * s, 2), round((ly1 - ly0) * s, 2))
    print(
        {k: (len(v), sum(map(len, v))) for k, v in groups.items()},
        "mm/px",
        round(s, 4),
        "size mm",
        size,
    )


if __name__ == "__main__":
    main()
