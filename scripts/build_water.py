#!/usr/bin/env python3
"""Build the course water: ponds + buffered creek channel.

Usage:
    python scripts/build_water.py green-hills
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, water


def main():
    cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "green-hills")
    cfg.ensure_dirs()
    print(f"== {cfg.name}: water (creek + ponds) ==")
    features = osm.parse(osm.fetch(cfg, force=True))  # refresh to include waterway
    polys = water.generate(cfg, features)
    out = water.write_geojson(cfg, polys)
    from collections import Counter
    kinds = Counter(k for k, _ in polys)
    print(f"water features: {dict(kinds)}")
    print("wrote", out)


if __name__ == "__main__":
    main()
