#!/usr/bin/env python3
"""High-resolution putting-surface contours from the LIDAR point cloud.

Usage:
    python scripts/build_greens.py green-hills
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, greens
from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox


def _save(cfg, results):
    arrays, meta = {}, []
    for r in results:
        arrays[f"green_{r['ref']:02d}"] = r["grid"].astype("float32")
        arrays[f"extent_{r['ref']:02d}"] = np.array(r["extent"])
        z = r["grid"][np.isfinite(r["grid"])]
        meta.append({"green": r["ref"], "gres_m": r["gres"],
                     "ground_points": r["n_ground"],
                     "density_ppm2": r["density_ppm2"],
                     "fall_m": round(float(z.max() - z.min()), 2) if z.size else None})
    np.savez_compressed(cfg.derived_dir / "greens_highres.npz", **arrays)
    (cfg.derived_dir / "greens_highres.json").write_text(
        json.dumps({"course": cfg.name, "crs_epsg": cfg.epsg, "greens": meta}, indent=2))
    return meta


def _contour_sheet(results, cfg, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(results)
    cols = 5
    rows = (n + cols - 1) // cols
    fig, axs = plt.subplots(rows, cols, figsize=(18, 3.4 * rows), dpi=110)
    axs = np.atleast_1d(axs).ravel()
    proj = Projector(cfg.epsg)
    for ax, r in zip(axs, results):
        Z = r["grid"]
        ux0, uy0, ux1, uy1 = r["extent"]
        finite = Z[np.isfinite(Z)]
        if finite.size < 5:
            ax.axis("off"); continue
        lv = np.arange(np.floor(finite.min() * 10) / 10, finite.max() + 0.1, 0.1)
        ax.contourf(Z, levels=lv, cmap="terrain", extent=[ux0, ux1, uy0, uy1], origin="upper")
        ax.contour(Z, levels=lv, colors="k", linewidths=0.3, alpha=0.5,
                   extent=[ux0, ux1, uy0, uy1], origin="upper")
        ring = [proj.xy(lo, la) for lo, la in r["geom"].exterior.coords]
        ax.plot([p[0] for p in ring], [p[1] for p in ring], "r-", lw=1.5)
        ax.set_title(f"G{r['ref']} · {r['density_ppm2']:.0f} pts/m² · 0.1 m lines",
                     fontsize=9)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")
    for ax in axs[len(results):]:
        ax.axis("off")
    fig.suptitle(f"{cfg.name} — high-res green contours (0.5 m LIDAR grid, 0.1 m lines)",
                 fontsize=15)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


def _compare(results, cfg, refs, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import rasterio
    proj = Projector(cfg.epsg)
    with rasterio.open(cfg.raw_dir / "dem.tif") as ds:
        dem = ds.read(1).astype(float)
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    cell = cfg.terrain_box_m / (dem.shape[0] - 1)
    rmap = {r["ref"]: r for r in results}
    fig, axs = plt.subplots(len(refs), 2, figsize=(10, 5 * len(refs)), dpi=120)
    axs = np.atleast_2d(axs)
    for row, ref in enumerate(refs):
        r = rmap.get(ref)
        if not r:
            continue
        ux0, uy0, ux1, uy1 = r["extent"]
        c0 = int((ux0 - xmin) / cell); c1 = int((ux1 - xmin) / cell)
        r1 = int((ymax - uy0) / cell); r0 = int((ymax - uy1) / cell)
        sub = dem[r0:r1, c0:c1]
        for ax, data, lab in ((axs[row, 0], sub, "1 m base DEM"),
                              (axs[row, 1], r["grid"], "0.5 m LIDAR (new)")):
            fin = data[np.isfinite(data)]
            lv = np.arange(np.floor(fin.min() * 10) / 10, fin.max() + 0.1, 0.1)
            ax.contourf(data, levels=lv, cmap="terrain", origin="upper")
            ax.contour(data, levels=lv, colors="k", linewidths=0.3, alpha=0.5, origin="upper")
            ax.set_title(f"Green {ref} — {lab}", fontsize=11)
            ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


def main():
    cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "green-hills")
    cfg.ensure_dirs()
    print(f"== {cfg.name}: high-res greens ==")
    features = osm.parse(osm.fetch(cfg))
    results = greens.highres(cfg, features)
    meta = _save(cfg, results)
    dens = [m["density_ppm2"] for m in meta]
    print(f"regridded {len(results)} greens at 0.5 m")
    print(f"  LIDAR density: median {sorted(dens)[len(dens)//2]:.0f} pts/m² "
          f"(min {min(dens):.0f}, max {max(dens):.0f})")
    _contour_sheet(results, cfg, cfg.preview_dir / "greens_highres_contours.png")
    _compare(results, cfg, [15, 17], cfg.preview_dir / "greens_compare.png")
    print("wrote greens_highres.npz/.json, greens_highres_contours.png, greens_compare.png")


if __name__ == "__main__":
    main()
