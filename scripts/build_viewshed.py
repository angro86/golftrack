#!/usr/bin/env python3
"""Per-hole viewshed to SFO / the bay / the city / the hills.

Usage:
    python scripts/build_viewshed.py green-hills
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, viewshed
from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox

LM_SHORT = {"SFO airport": "SFO", "SF Bay": "Bay", "Downtown SF": "City",
            "San Bruno Mtn": "SanBruno", "West hills": "Hills"}


def context_map(wt, cfg, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    dy, dx = np.gradient(wt.z, wt.cell)
    slope = np.pi / 2 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    hs = np.clip(np.sin(np.radians(45)) * np.sin(slope) +
                 np.cos(np.radians(45)) * np.cos(slope) * np.cos(np.radians(315) - aspect),
                 0, 1)
    fig, ax = plt.subplots(figsize=(12, 12), dpi=130)
    ax.imshow(hs, cmap="gray", extent=[0, wt.n, wt.n, 0])
    ax.imshow(wt.z, cmap="terrain", alpha=0.35, extent=[0, wt.n, wt.n, 0])

    def px(x, y):
        return ((x - wt.xmin) / wt.cell, (wt.ymax - y) / wt.cell)
    ccx, ccy = px(wt.cx, wt.cy)
    ax.plot(ccx, ccy, "o", color="#d11", ms=10, zorder=5)
    ax.text(ccx, ccy - 30, "Green Hills CC", color="#d11", fontsize=11,
            fontweight="bold", ha="center", zorder=6)
    proj = Projector(cfg.epsg)
    for name, (lat, lon, _te) in viewshed.LANDMARKS.items():
        lx, ly = px(*proj.xy(lon, lat))
        if not (0 <= lx <= wt.n and 0 <= ly <= wt.n):
            continue  # landmark beyond the DEM frame
        ax.plot([ccx, lx], [ccy, ly], "-", color="#1f77ff", lw=1.0, alpha=0.6, zorder=4)
        ax.plot(lx, ly, "^", color="#1f77ff", ms=8, zorder=5)
        ax.text(lx, ly - 25, name, color="#0a3", fontsize=10, fontweight="bold",
                ha="center", zorder=6)
    ax.set_xlim(0, wt.n); ax.set_ylim(wt.n, 0)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{cfg.name} — surroundings ({viewshed.WIDE_BOX_M//1000} km context)")
    fig.tight_layout(); fig.savefig(out_path, bbox_inches="tight"); plt.close(fig)


def holes_map(rows, features, cfg, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    proj = Projector(cfg.epsg)
    (xmin, ymin, xmax, ymax), (cx, cy) = utm_bbox(cfg)
    rmap = {r["ref"]: r for r in rows}
    fig, ax = plt.subplots(figsize=(12, 12), dpi=130)
    ax.set_facecolor("#eef0e6")
    for f in features:
        if f["category"] != "hole" or not f["tags"].get("ref", "").isdigit():
            continue
        ref = int(f["tags"]["ref"])
        xy = [proj.xy(lo, la) for lo, la in f["geom"].coords]
        v = rmap.get(ref, {}).get("views", {})
        sees = [LM_SHORT[k] for k in ("SFO airport", "SF Bay", "Downtown SF")
                if v.get(k, {}).get("visible")]
        color = "#e8731c" if sees else "#3a7d3a"
        ax.plot([p[0] for p in xy], [p[1] for p in xy], color=color, lw=2.5)
        mid = xy[len(xy) // 2]
        label = f"{ref}" + (" " + "/".join(sees) if sees else "")
        ax.text(mid[0], mid[1], label, fontsize=8, fontweight="bold", ha="center",
                va="center", color="#111",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=1))
    r = cfg.terrain_box_m / 2
    ax.set_xlim(cx - r, cx + r); ax.set_ylim(cy - r, cy + r)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{cfg.name} — per-hole views\n"
                 f"orange = sees SFO/Bay/City   green = framed by hills/trees")
    fig.tight_layout(); fig.savefig(out_path, bbox_inches="tight"); plt.close(fig)


def main():
    cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "green-hills")
    cfg.ensure_dirs()
    print(f"== {cfg.name}: per-hole viewshed ==")
    features = osm.parse(osm.fetch(cfg))
    wt, rows = viewshed.analyze(cfg, features)
    (cfg.derived_dir / "viewshed.json").write_text(json.dumps(
        {"course": cfg.name, "holes": rows}, indent=2))

    order = ["SFO airport", "SF Bay", "Downtown SF"]
    print(f"{'Hole':>4} {'Faces':>6}  " + " ".join(f"{LM_SHORT[k]:>8}" for k in order))
    for r in rows:
        cells = []
        for k in order:
            vv = r["views"][k]
            mark = ("see" if vv["visible"] else " - ") + ("^" if vv["visible"] and vv["ahead"] else " ")
            cells.append(f"{mark:>8}")
        print(f"{r['ref']:>4} {r['play_bearing']:>5}°  " + " ".join(cells))
    print("  (see = visible, ^ = in the direction you're playing)")

    context_map(wt, cfg, cfg.preview_dir / "viewshed_context.png")
    holes_map(rows, features, cfg, cfg.preview_dir / "viewshed_holes.png")
    print("wrote viewshed.json, viewshed_context.png, viewshed_holes.png")


if __name__ == "__main__":
    main()
