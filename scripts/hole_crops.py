#!/usr/bin/env python3
"""Per-hole validation crops: aerial + detected trees + splines, for QA against
the GPS-app hole views.

Usage:
    python scripts/hole_crops.py green-hills            # all 18
    python scripts/hole_crops.py green-hills --holes 7 15 16
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, fairways, tees
from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox
from gspro_course.splines import LAYERS, LINE_LAYERS

BUF_M = 65
TREE_COLORS = {"tall": "#0b3d0b", "mid": "#1f8f1f", "shrub": "#9acd32"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course")
    ap.add_argument("--holes", type=int, nargs="*", default=list(range(1, 19)))
    args = ap.parse_args()
    cfg = config.load(args.course)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    rgb = np.asarray(Image.open(cfg.raw_dir / "naip.png").convert("RGB"))
    px = rgb.shape[0]
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    box = cfg.terrain_box_m
    proj = Projector(cfg.epsg)

    def to_px(x, y):
        return ((x - xmin) / box * px, (ymax - y) / box * px)

    trees = json.loads((cfg.derived_dir / "trees.json").read_text())["trees"]
    features = [f for f in osm.parse(osm.fetch(cfg)) if f["category"] != "fairway"]
    features += fairways.load_generated(cfg) + tees.load(cfg)
    holes = {int(f["tags"]["ref"]): f for f in features
             if f["category"] == "hole" and f["tags"].get("ref", "").isdigit()}
    # black tee box coords per hole, to widen the crop to include them
    blacktee = {}
    for f in features:
        if f["category"] == "tee" and f["tags"].get("tee") == "black" \
                and f["tags"].get("ref", "").isdigit():
            blacktee.setdefault(int(f["tags"]["ref"]), []).extend(
                proj.xy(lon, lat) for lon, lat in f["geom"].exterior.coords)
    par = {h["ref"]: h["par"] for h in
           json.loads((cfg.derived_dir / "holes.json").read_text())["holes"]}

    outdir = cfg.preview_dir / "holes"
    outdir.mkdir(exist_ok=True)
    for hn in args.holes:
        if hn not in holes:
            continue
        cl = [proj.xy(lon, lat) for lon, lat in holes[hn]["geom"].coords]
        pts_xy = cl + blacktee.get(hn, [])
        xs = [p[0] for p in pts_xy]; ys = [p[1] for p in pts_xy]
        bx0, bx1 = min(xs) - BUF_M, max(xs) + BUF_M
        by0, by1 = min(ys) - BUF_M, max(ys) + BUF_M

        fig, ax = plt.subplots(figsize=(7, 10), dpi=130)
        ax.imshow(rgb, extent=[0, px, px, 0], zorder=0)
        # splines in view
        for f in features:
            spec = LAYERS.get(f["category"])
            if not spec:
                continue
            layer, _fill, stroke, _s = spec
            g = f["geom"]
            coords = (list(g.exterior.coords) if g.geom_type == "Polygon"
                      else list(g.coords))
            pts = [to_px(*proj.xy(lon, lat)) for lon, lat in coords]
            if layer == "centerline":
                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                        color="#fff", lw=1.5, ls="--", zorder=4)
            elif layer in LINE_LAYERS:
                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                        color=stroke, lw=1.0, zorder=2, alpha=0.8)
            else:
                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                        color=stroke, lw=1.6, zorder=3)
        # trees in view
        for t in trees:
            if not (bx0 <= t["x_utm"] <= bx1 and by0 <= t["y_utm"] <= by1):
                continue
            cx, cy = to_px(t["x_utm"], t["y_utm"])
            r = max(t["crown_radius_m"] / box * px, 2)
            ax.add_patch(plt.Circle((cx, cy), r, fill=False,
                         color=TREE_COLORS[t["bucket"]], lw=1.0, zorder=5))

        p0 = to_px(bx0, by1); p1 = to_px(bx1, by0)
        ax.set_xlim(p0[0], p1[0]); ax.set_ylim(p1[1], p0[1])
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{cfg.name} — Hole {hn} (par {par.get(hn,'?')})\n"
                     f"aerial + LIDAR trees + splines (north up)", fontsize=11)
        fig.tight_layout()
        out = outdir / f"hole_{hn:02d}.png"
        fig.savefig(out, bbox_inches="tight"); plt.close(fig)
        print("wrote", out)


if __name__ == "__main__":
    main()
