#!/usr/bin/env python3
"""Render the full assembled course on the aerial — fairways, greens, bunkers,
water, tees (+ black tees), trees, hole lines & numbers.

Usage:
    python scripts/master_map.py green-hills
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, fairways, tees, water
from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox

_REPLACED = {"fairway", "water", "water_hazard", "lateral_water_hazard", "creek"}
STYLE = {  # category -> (facecolor, edgecolor, alpha, lw)
    "fairway": ("#d8e84a", "#b6c61f", 0.40, 0.6),
    "green":   ("#2f8f2f", "#16521a", 0.75, 0.8),
    "tee":     ("#46c246", "#1c5a1c", 0.85, 0.6),
    "bunker":  ("#f2e4ad", "#cdb86a", 0.85, 0.6),
    "water":   ("#3aa0e0", "#1565a8", 0.70, 0.6),
}


def main():
    cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "green-hills")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    img = Image.open(cfg.raw_dir / "naip.png").convert("RGB")
    if img.width > 2200:
        img = img.resize((2200, 2200))
    rgb = np.asarray(img)
    px = rgb.shape[0]
    (xmin, ymin, xmax, ymax), (cx, cy) = utm_bbox(cfg)
    box = cfg.terrain_box_m
    proj = Projector(cfg.epsg)

    def tp(lon, lat):
        x, y = proj.xy(lon, lat)
        return ((x - xmin) / box * px, (ymax - y) / box * px)

    features = [f for f in osm.parse(osm.fetch(cfg)) if f["category"] not in _REPLACED]
    features += fairways.load_generated(cfg) + water.load(cfg)
    black = tees.load(cfg)

    fig, ax = plt.subplots(figsize=(13, 13), dpi=110)
    ax.imshow(rgb, extent=[0, px, px, 0], zorder=0)

    # trees first (under playing surfaces) — one scatter, not 12k patches
    tj = cfg.derived_dir / "trees.json"
    if tj.exists():
        col = {"tall": "#0b3d0b", "mid": "#1f8f1f", "shrub": "#86c232"}
        ts = json.loads(tj.read_text())["trees"]
        xs, ys, cs, ss = [], [], [], []
        for t in ts:
            x, y = tp(t["lon"], t["lat"])
            xs.append(x); ys.append(y); cs.append(col[t["bucket"]])
            ss.append((max(t["crown_radius_m"], 2.0)) ** 2 * 0.6)
        ax.scatter(xs, ys, s=ss, c=cs, alpha=0.5, edgecolors="none", zorder=1)

    zorder = {"fairway": 2, "water": 3, "bunker": 4, "green": 5, "tee": 5}
    for f in features:
        st = STYLE.get(f["category"])
        if not st or f["geom"].geom_type != "Polygon":
            continue
        fc, ec, a, lw = st
        xy = [tp(lo, la) for lo, la in f["geom"].exterior.coords]
        ax.add_patch(plt.Polygon(xy, closed=True, fc=fc, ec=ec, lw=lw, alpha=a,
                                 zorder=zorder.get(f["category"], 3)))

    for b in black:  # championship tees
        xy = [tp(lo, la) for lo, la in b["geom"].exterior.coords]
        ax.add_patch(plt.Polygon(xy, closed=True, fc="#111", ec="#fff", lw=1.0,
                                 zorder=6))

    for f in features:
        if f["category"] != "hole" or not f["tags"].get("ref", "").isdigit():
            continue
        xy = [tp(lo, la) for lo, la in f["geom"].coords]
        ax.plot([p[0] for p in xy], [p[1] for p in xy], color="#fff", lw=1.2,
                ls=(0, (4, 3)), zorder=7, alpha=0.85)
        mid = xy[len(xy) // 2]
        ax.text(mid[0], mid[1], f["tags"]["ref"], fontsize=9, fontweight="bold",
                ha="center", va="center", zorder=8,
                bbox=dict(boxstyle="circle,pad=0.18", fc="white", ec="#333", lw=0.6))

    ax.set_xlim(0, px); ax.set_ylim(px, 0)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{cfg.name} — full assembled course\n"
                 f"fairways · greens · 69 bunkers · creek+ponds · "
                 f"black tees · 12,400 trees", fontsize=15)
    out = cfg.preview_dir / "master_plan.png"
    fig.savefig(out); plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    main()
