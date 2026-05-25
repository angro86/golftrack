"""Render a course layout preview PNG from parsed OSM features."""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon

from gspro_course.geo import Projector, compass_bearing

# draw order + styling per category (zorder low -> high)
STYLE = {
    "building":    dict(fc="#d9d4cc", ec="#b8b2a8", lw=0.3, z=1),
    "course_boundary": dict(fc="none", ec="#7a8b5a", lw=1.2, z=2, ls="--"),
    "rough":       dict(fc="#9fb46e", ec="none", z=3),
    "fairway":     dict(fc="#bfe08a", ec="none", z=4),
    "driving_range": dict(fc="#bfe08a", ec="none", z=4),
    "water":       dict(fc="#8fc4e8", ec="#5a9bd4", lw=0.4, z=5),
    "water_hazard": dict(fc="#8fc4e8", ec="#5a9bd4", lw=0.4, z=5),
    "lateral_water_hazard": dict(fc="#8fc4e8", ec="#5a9bd4", lw=0.4, z=5),
    "bunker":      dict(fc="#f2e6b8", ec="#d8c98a", lw=0.4, z=6),
    "green":       dict(fc="#4f9d4f", ec="#2f6e2f", lw=0.5, z=7),
    "tee":         dict(fc="#5fae5f", ec="#2f6e2f", lw=0.4, z=7),
    "clubhouse":   dict(fc="#c98f6a", ec="#8a5a3a", lw=0.6, z=8),
}


def _add_poly(ax, geom, proj, style):
    xy = proj.ring_xy(list(geom.exterior.coords))
    ax.add_patch(MplPolygon(xy, closed=True, **{k: v for k, v in style.items() if k != "z"},
                            zorder=style.get("z", 1)))


def render(features, report, cfg, out_path):
    proj = Projector(cfg.epsg)
    cx, cy = proj.xy(cfg.lon, cfg.lat)

    fig, ax = plt.subplots(figsize=(14, 14), dpi=130)
    ax.set_facecolor("#eef0e6")

    for f in features:
        cat = f["category"]
        base = cat.split(":")[0]
        style = STYLE.get(base)
        g = f["geom"]
        if style and g.geom_type == "Polygon":
            _add_poly(ax, g, proj, style)
        elif base == "cartpath" or base == "path":
            xy = proj.ring_xy(list(g.coords))
            ax.plot([p[0] for p in xy], [p[1] for p in xy],
                    color="#cfc3a8", lw=1.0, zorder=5)
        elif base.startswith("aeroway"):
            xy = proj.ring_xy(list(g.coords) if g.geom_type == "LineString"
                              else list(g.exterior.coords))
            ax.plot([p[0] for p in xy], [p[1] for p in xy],
                    color="#999", lw=1.0, zorder=2)

    # hole centerlines + numbers
    for f in features:
        if f["category"] != "hole":
            continue
        xy = proj.ring_xy(list(f["geom"].coords))
        xs = [p[0] for p in xy]; ys = [p[1] for p in xy]
        ax.plot(xs, ys, color="#444", lw=1.0, ls=":", zorder=9, alpha=0.7)
        ref = f["tags"].get("ref", "")
        mid = xy[len(xy) // 2]
        ax.text(mid[0], mid[1], str(ref), fontsize=9, fontweight="bold",
                color="#222", ha="center", va="center", zorder=10,
                bbox=dict(boxstyle="circle,pad=0.2", fc="white", ec="#444", lw=0.6))

    # window centered on course
    r = cfg.course_radius_m
    ax.set_xlim(cx - r, cx + r)
    ax.set_ylim(cy - r, cy + r)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])

    # north arrow
    ax.annotate("N", xy=(cx - r * 0.9, cy + r * 0.9),
                xytext=(cx - r * 0.9, cy + r * 0.72),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.5),
                ha="center", fontsize=12, fontweight="bold")

    # scale bar (200 m)
    sb = 200
    x0 = cx + r * 0.45; y0 = cy - r * 0.92
    ax.plot([x0, x0 + sb], [y0, y0], color="black", lw=2)
    ax.text(x0 + sb / 2, y0 + r * 0.02, "200 m", ha="center", fontsize=9)

    # landmark direction arrows (SFO, downtown SF)
    for name, ll in cfg.landmarks.items():
        b = compass_bearing((cx, cy), proj.xy(ll["lon"], ll["lat"]))
        ang = math.radians(b)
        ex = cx + math.sin(ang) * r * 0.95
        ey = cy + math.cos(ang) * r * 0.95
        ax.annotate(f"→ {name}", xy=(ex, ey),
                    xytext=(cx + math.sin(ang) * r * 0.6, cy + math.cos(ang) * r * 0.6),
                    arrowprops=dict(arrowstyle="-|>", color="#b0451f", lw=1.8),
                    color="#b0451f", fontsize=10, fontweight="bold",
                    ha="center", va="center", zorder=11)

    title = f"{cfg.name} — layout from OpenStreetMap"
    sub = f"{report['holes_found']} holes · {report['total_yards']} yd · par {report['total_par']} · {cfg.architect}"
    ax.set_title(f"{title}\n{sub}", fontsize=14)

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path
