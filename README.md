# golftrack — GSPro course builder

Build real golf courses for the **GSPro** simulator from public data, automating
as much of the pipeline as possible before the manual OPCD/Unity polish.

First target course: **Green Hills Country Club**, Millbrae CA (Alister MacKenzie, 1930).

## Why this exists

GSPro only loads courses built with the OPCD toolchain (Blender + Inkscape +
Unity + GreenKeeper), and the final 3D assembly is manual. This repo automates
everything *upstream* of that so the Unity build starts mostly done:

| Phase | Output | Status |
|-------|--------|--------|
| acquire | OSM features, USGS LIDAR, NAIP aerial | OSM done |
| terrain | bare-earth heightmap (OPCD/Unity ready) | next |
| features | golf polygons → pre-traced Inkscape splines (SVG) | geojson done |
| trees | LIDAR canopy → individual tree positions (Arborist) | planned |
| scenery | surrounding buildings / airport / water | data pulled |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
# Pull OSM data, write features.geojson + hole report + preview PNG
.venv/bin/python scripts/build_layout.py green-hills
```

Outputs land in `courses/<slug>/`:
- `raw/` — downloaded source data (gitignored)
- `derived/` — geojson, hole report, (later) heightmaps + spline SVGs
- `preview/` — layout PNG

## Data sources

- **OpenStreetMap** (Overpass API) — fairways, greens, tees, bunkers, holes, water, buildings
- **USGS 3DEP LIDAR** (Entwine Point Tiles on AWS) — terrain + tree canopy
- **USDA NAIP** — aerial imagery overlay

Course parameters live in `config/<slug>.yaml`.
