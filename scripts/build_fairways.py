#!/usr/bin/env python3
"""Generate fairway polygons for holes OSM didn't map.

Usage:
    python scripts/build_fairways.py green-hills
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, fairways


def main():
    cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "green-hills")
    cfg.ensure_dirs()
    print(f"== {cfg.name}: generate missing fairways ==")
    features = osm.parse(osm.fetch(cfg))
    osm_fw = sum(1 for f in features if f["category"] == "fairway")
    results = fairways.generate(cfg, features)
    out = fairways.write_geojson(cfg, results)
    gen_holes = sorted(ref for ref, _ in results)
    print(f"OSM fairways kept: {osm_fw} | generated: {len(results)} "
          f"for holes {gen_holes}")
    print("wrote", out)


if __name__ == "__main__":
    main()
