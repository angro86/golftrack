"""Convert OSM golf features into Inkscape-layered SVG splines.

The SVG canvas matches the terrain heightmap exactly: a `box_m` square where
1 user-unit = 1 meter and (0,0) is the top-left (xmin, ymax) in the projected
CRS. Importing the heightmap/aerial at the same size puts every spline in the
right spot. Organic features are smoothed with Catmull-Rom -> cubic beziers.
"""
from xml.sax.saxutils import escape

from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox

# OSM golf category -> (layer name, fill, stroke, smooth?)
LAYERS = {
    "course_boundary": ("boundary", "none", "#202020", False),
    "rough": ("rough", "#9fb46e", "#7a8b5a", True),
    "fairway": ("fairway", "#bfe08a", "#8fb05a", True),
    "driving_range": ("fairway", "#bfe08a", "#8fb05a", True),
    "water": ("water", "#8fc4e8", "#5a9bd4", True),
    "water_hazard": ("water", "#8fc4e8", "#5a9bd4", True),
    "lateral_water_hazard": ("water", "#8fc4e8", "#5a9bd4", True),
    "bunker": ("bunker", "#f2e6b8", "#d8c98a", True),
    "green": ("green", "#4f9d4f", "#2f6e2f", True),
    "tee": ("tee", "#5fae5f", "#2f6e2f", False),
    "clubhouse": ("structures", "#c98f6a", "#8a5a3a", False),
    "cartpath": ("cartpath", "none", "#cfc3a8", False),
    "path": ("cartpath", "none", "#cfc3a8", False),
    "hole": ("centerline", "none", "#cc2222", False),
}
# bottom -> top stacking order
LAYER_ORDER = ["boundary", "rough", "fairway", "water", "bunker", "green",
               "tee", "structures", "cartpath", "centerline"]
LINE_LAYERS = {"cartpath", "centerline"}
MIN_SMOOTH_PTS = 6


def _catmull_rom(points):
    """Closed Catmull-Rom -> list of cubic bezier segments (p0,c1,c2,p1)."""
    n = len(points)
    segs = []
    for i in range(n):
        p_prev = points[(i - 1) % n]
        p0 = points[i]
        p1 = points[(i + 1) % n]
        p_next = points[(i + 2) % n]
        c1 = (p0[0] + (p1[0] - p_prev[0]) / 6.0, p0[1] + (p1[1] - p_prev[1]) / 6.0)
        c2 = (p1[0] - (p_next[0] - p0[0]) / 6.0, p1[1] - (p_next[1] - p0[1]) / 6.0)
        segs.append((p0, c1, c2, p1))
    return segs


def _fmt(v):
    return f"{v:.2f}"


def _ring_pts(geom, to_svg):
    coords = list(geom.exterior.coords) if geom.geom_type == "Polygon" \
        else list(geom.coords)
    pts = [to_svg(lon, lat) for lon, lat in coords]
    # drop duplicate closing vertex for cyclic smoothing
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _path_d(geom, to_svg, smooth, closed):
    pts = _ring_pts(geom, to_svg)
    if len(pts) < 2:
        return None
    if smooth and closed and len(pts) >= MIN_SMOOTH_PTS:
        segs = _catmull_rom(pts)
        d = f"M {_fmt(segs[0][0][0])},{_fmt(segs[0][0][1])} "
        d += " ".join(
            f"C {_fmt(c1[0])},{_fmt(c1[1])} {_fmt(c2[0])},{_fmt(c2[1])} "
            f"{_fmt(p1[0])},{_fmt(p1[1])}" for (_p0, c1, c2, p1) in segs)
        return d + " Z"
    d = f"M {_fmt(pts[0][0])},{_fmt(pts[0][1])} "
    d += " ".join(f"L {_fmt(x)},{_fmt(y)}" for x, y in pts[1:])
    return d + (" Z" if closed else "")


def build(features, cfg, out_path):
    proj = Projector(cfg.epsg)
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    size = cfg.terrain_box_m

    def to_svg(lon, lat):
        x, y = proj.xy(lon, lat)
        return (x - xmin, ymax - y)

    # group path strings per layer
    by_layer = {name: [] for name in LAYER_ORDER}
    counts = {}
    for f in features:
        spec = LAYERS.get(f["category"])
        if not spec:
            continue
        layer, fill, stroke, smooth = spec
        closed = layer not in LINE_LAYERS
        d = _path_d(f["geom"], to_svg, smooth, closed)
        if d is None:
            continue
        sw = 0.8 if layer in LINE_LAYERS or fill == "none" else 0.4
        dash = ' stroke-dasharray="6,4"' if layer == "centerline" else ""
        by_layer[layer].append(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"{dash}/>')
        counts[layer] = counts.get(layer, 0) + 1

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        f'width="{size}" height="{size}" viewBox="0 0 {size} {size}">',
        f'<title>{escape(cfg.name)} — course splines (1 unit = 1 m)</title>',
        f'<rect x="0" y="0" width="{size}" height="{size}" fill="#eef0e6"/>',
    ]
    for layer in LAYER_ORDER:
        if not by_layer[layer]:
            continue
        parts.append(f'<g inkscape:groupmode="layer" inkscape:label="{layer}" '
                     f'id="{layer}">')
        parts.extend(by_layer[layer])
        parts.append('</g>')
    parts.append('</svg>')
    out_path.write_text("\n".join(parts))
    return counts


def render_preview(features, cfg, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.path import Path as MplPath
    from matplotlib.patches import PathPatch

    proj = Projector(cfg.epsg)
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    size = cfg.terrain_box_m

    def to_svg(lon, lat):
        x, y = proj.xy(lon, lat)
        return (x - xmin, ymax - y)

    fig, ax = plt.subplots(figsize=(13, 13), dpi=130)
    ax.set_facecolor("#eef0e6")
    z = {n: i for i, n in enumerate(LAYER_ORDER)}

    for f in features:
        spec = LAYERS.get(f["category"])
        if not spec:
            continue
        layer, fill, stroke, smooth = spec
        closed = layer not in LINE_LAYERS
        pts = _ring_pts(f["geom"], to_svg)
        if len(pts) < 2:
            continue
        if smooth and closed and len(pts) >= MIN_SMOOTH_PTS:
            segs = _catmull_rom(pts)
            verts = [segs[0][0]]
            codes = [MplPath.MOVETO]
            for _p0, c1, c2, p1 in segs:
                verts += [c1, c2, p1]
                codes += [MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4]
            verts.append(segs[0][0]); codes.append(MplPath.CLOSEPOLY)
            patch = PathPatch(MplPath(verts, codes),
                              facecolor=(fill if fill != "none" else "none"),
                              edgecolor=stroke, lw=0.6, zorder=z[layer] + 1)
            ax.add_patch(patch)
        else:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if closed:
                ax.fill(xs, ys, facecolor=(fill if fill != "none" else "none"),
                        edgecolor=stroke, lw=0.6, zorder=z[layer] + 1,
                        closed=True)
            else:
                ax.plot(xs, ys, color=stroke, lw=1.0, zorder=z[layer] + 1,
                        ls=("--" if layer == "centerline" else "-"))

    ax.set_xlim(0, size); ax.set_ylim(size, 0)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{cfg.name} — pre-traced splines (smoothed)\n"
                 f"SVG aligned to heightmap · {size} m · 1 unit = 1 m",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path
