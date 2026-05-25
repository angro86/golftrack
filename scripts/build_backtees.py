#!/usr/bin/env python3
"""Place the missing championship (black) tee boxes.

Writes an editable override file (config/<slug>-black-tees.yaml) seeded with
auto-estimates; edit the lat/lon there for exact, locally-known positions.

Usage:
    python scripts/build_backtees.py green-hills
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, tees


def main():
    cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "green-hills")
    cfg.ensure_dirs()
    print(f"== {cfg.name}: championship tee boxes ==")
    features = osm.parse(osm.fetch(cfg))

    est = tees.auto_estimate(cfg, features)
    tmpl = tees.write_template(cfg, est)
    print(f"holes needing a back tee: {[e['ref'] for e in est]}")
    for e in est:
        print(f"  hole {e['ref']:>2}: auto lat {e['lat']}, lon {e['lon']} "
              f"(+{e['gap_yd']} yd back -> card {e['card_yd']})")
    print(f"edit exact positions in: {tmpl}")

    results = tees.generate(cfg, features)
    out = tees.write_geojson(cfg, results)
    man = [r["ref"] for r in results if r["source"] == "manual"]
    print(f"tee boxes: {len(results)} ({'manual: ' + str(man) if man else 'all auto'})")
    print("wrote", out)


if __name__ == "__main__":
    main()
