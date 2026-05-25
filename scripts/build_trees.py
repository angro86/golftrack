#!/usr/bin/env python3
"""Phase trees: USGS LIDAR -> canopy height model -> individual trees.

Usage:
    python scripts/build_trees.py green-hills
"""
import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, lidar
from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox


def render_chm(chm, cfg, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(12, 12), dpi=120)
    im = ax.imshow(chm, cmap="YlGn", vmin=0, vmax=30)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{cfg.name} — canopy height model (m), buildings masked")
    fig.colorbar(im, ax=ax, fraction=0.046, shrink=0.8, label="canopy height (m)")
    fig.tight_layout(); fig.savefig(out_path, bbox_inches="tight"); plt.close(fig)


def render_trees_on_aerial(trees, cfg, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    aerial = cfg.raw_dir / "naip.png"
    if not aerial.exists():
        return None
    rgb = np.asarray(Image.open(aerial).convert("RGB"))
    px = rgb.shape[0]
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    box = cfg.terrain_box_m
    colors = {"tall": "#0b3d0b", "mid": "#1f8f1f", "shrub": "#9acd32"}

    fig, ax = plt.subplots(figsize=(14, 14), dpi=150)
    ax.imshow(rgb, extent=[0, px, px, 0], zorder=0)
    for t in trees:
        cx = (t["x_utm"] - xmin) / box * px
        cy = (ymax - t["y_utm"]) / box * px
        r = max(t["crown_radius_m"] / box * px, 1.5)
        ax.add_patch(plt.Circle((cx, cy), r, fill=False,
                                color=colors[t["bucket"]], lw=0.6, alpha=0.8))
    ax.set_xlim(0, px); ax.set_ylim(px, 0)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{cfg.name} — {len(trees)} detected trees over NAIP aerial\n"
                 f"(dark=tall  mid=green  light=shrub)")
    fig.tight_layout(); fig.savefig(out_path, bbox_inches="tight"); plt.close(fig)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course")
    args = ap.parse_args()
    cfg = config.load(args.course)
    cfg.ensure_dirs()
    print(f"== {cfg.name}: LIDAR tree detection ==")

    features = osm.parse(osm.fetch(cfg))
    t0 = time.time()
    chm, cell, n_nodes, n_pts = lidar.build_chm(cfg, features)
    print(f"streamed {n_nodes} EPT nodes, {n_pts:,} points "
          f"-> CHM {chm.shape} @ {cell:.2f} m/cell ({time.time()-t0:.0f}s)")

    trees = lidar.detect_trees(cfg, chm, cell)
    buckets = Counter(t["bucket"] for t in trees)
    print(f"detected {len(trees)} trees: {dict(buckets)}")
    if trees:
        hs = [t["height_m"] for t in trees]
        print(f"  height: min {min(hs)} / median {sorted(hs)[len(hs)//2]} / max {max(hs)} m")

    cols = ["x_utm", "y_utm", "lon", "lat", "height_m", "crown_radius_m", "bucket"]
    with open(cfg.derived_dir / "trees.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(trees)
    (cfg.derived_dir / "trees.json").write_text(json.dumps(
        {"course": cfg.name, "count": len(trees), "buckets": dict(buckets),
         "trees": trees}))
    print("wrote", cfg.derived_dir / "trees.csv")

    render_chm(chm, cfg, cfg.preview_dir / "chm.png")
    render_trees_on_aerial(trees, cfg, cfg.preview_dir / "trees.png")
    print("wrote previews: chm.png, trees.png")


if __name__ == "__main__":
    main()
