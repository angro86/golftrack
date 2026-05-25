#!/usr/bin/env python3
"""Per-footprint building heights from LIDAR.

Usage:
    python scripts/build_buildings.py green-hills
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, buildings


def main():
    cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "green-hills")
    cfg.ensure_dirs()
    print(f"== {cfg.name}: building heights ==")
    features = osm.parse(osm.fetch(cfg))
    bs = buildings.compute(cfg, features)
    out = buildings.write_geojson(cfg, bs)
    hs = sorted(b["height_m"] for b in bs)
    club = next((b for b in bs if b["kind"] == "clubhouse"), None)
    print(f"buildings: {len(bs)}  ({sum(b['in_course'] for b in bs)} inside the course)")
    if hs:
        print(f"  heights m: min {hs[0]} / median {hs[len(hs)//2]} / max {hs[-1]}")
    if club:
        print(f"  clubhouse: {club['area_m2']} m2, {club['height_m']} m "
              f"(~{club['levels']} levels)")
    print("wrote", out)


if __name__ == "__main__":
    main()
