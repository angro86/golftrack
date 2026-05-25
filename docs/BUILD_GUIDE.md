# Green Hills CC — GSPro build guide

How to turn the data this repo generated into a playable GSPro course. The hard
data work (terrain, fairways, trees, tees, water, scenery) is done; this walks
through the **manual OPCD/Unity assembly** that GSPro requires.

> Reality check: GSPro only loads courses built with the **OPCD** toolchain, and
> the final 3D assembly happens in the Unity editor by hand. There is no script
> that emits a finished GSPro course. What we've done is make every input ready
> so you're *assembling*, not creating from scratch. Where a number or UI detail
> below is marked **(confirm)**, verify it against the current OPCD V4 docs —
> the toolset evolves and I can't see your screen.

---

## 0. What you already have (the inputs)

Everything lives in `courses/green-hills/`:

| File | What it is | Feeds OPCD step |
|---|---|---|
| `derived/heightmap.png` / `.raw` | 16-bit terrain heightmap, 2049×2049 | Terrain import |
| `derived/terrain_meta.json` | exact terrain size/height numbers | Terrain settings |
| `raw/naip.png` | 0.3 m aerial (regenerate: `build_imagery.py`) | Tracing overlay + textures |
| `derived/splines.svg` | Inkscape-layered course splines | Splining |
| `derived/fairways.geojson` | aerial-detected fairway shapes | Surface painting |
| `derived/water.geojson` | creek channel + 2 ponds | Water shaping |
| `derived/trees.csv` | 12,409 trees: lat/lon, height, crown, bucket | Arborist |
| `derived/buildings.geojson` | 3,534 footprints + heights, clubhouse flagged | Object placement |
| `derived/back_tees.geojson` | the 5 championship tee boxes (2/5/6/17/18) | Tee markers |
| `derived/viewshed.json` | which holes see SFO/bay/city | Distant scenery |
| `derived/course_data.json` | per-hole par/HCP/yards/tees/pin/bearing | GreenKeeper |

**Key numbers (from `terrain_meta.json`):**
- Terrain size: **2048 m × 2048 m**, heightmap **2049×2049**, **1.0 m/pixel**
- Terrain height (0→white): **167.88 m** (elevation −0.53 → 167.35 m)
- Projected CRS: **EPSG:32610 (UTM zone 10N)** — the frame everything shares
- Course: Black/Blue Combo **6,428 yd, par 71, 72.2 / 143**

---

## 1. Prerequisites (one-time)

On a **Windows PC** with a decent GPU:

1. **GSPro** (paid subscription) — the simulator itself.
2. **Unity** — the exact version OPCD V4 requires **(confirm on the OPCD download page)**.
3. **OPCD V4 toolset** — the Unity package + GreenKeeper. (GSPro 3rd-party tools page / OPCD Discord.)
4. **Blender** + the **OPCD Blender add-on** — bunkers/water/terrain ops.
5. **Inkscape** — splining.
6. **OPCD Arborist** — vegetation planting.
7. *(optional)* **QGIS** — only if you want to inspect the GeoTIFFs/GeoJSON.

Join the OPCD/GSPro course-design Discord — it's where the current toolset,
versions, and gotchas live.

---

## 2. Project + terrain

1. Create a new OPCD course project in Unity (follow the OPCD "new course" steps).
2. Add a Unity **Terrain**. Set:
   - **Heightmap Resolution: 2049**
   - **Terrain Width / Length: 2048 / 2048** (meters)
   - **Terrain Height: 168** (use 167.88 from `terrain_meta.json`)
3. **Import Raw**: `derived/heightmap.raw` — 16-bit, **Windows (little-endian)** byte
   order, resolution **2049×2049**. (Or import `heightmap.png` if your flow prefers PNG.)
4. The terrain now matches Green Hills' real relief (hills west, dropping ~168 m
   toward the bay east). Spot-check: the west edge should be the high ground.

> Orientation: the heightmap is **north-up** in UTM 10N. Keep the terrain
> north-aligned so the sun/skybox and the viewshed bearings stay correct.

---

## 3. Aerial overlay (your tracing canvas)

Import `raw/naip.png` as a reference texture/decal sized to the **full 2048 m**
terrain, top-left aligned to the terrain origin. Because the aerial, heightmap,
and splines all share the UTM box, it drops in 1:1. You'll trace/verify against
this and reuse it for ground-texture cues.

---

## 4. Splines (greens, tees, bunkers, fairways, cart paths, water)

1. Open `derived/splines.svg` in **Inkscape**. Layers are pre-named:
   `boundary, rough, fairway, water, bunker, green, tee, structures, cartpath, centerline`.
2. The polygons are already drawn to scale (1 SVG unit = 1 m), organic features
   smoothed. Bring them into the OPCD splining workflow per layer **(confirm the
   exact OPCD import path — usually copy/clean each layer into the OPCD template)**.
3. Paint the surface types onto the terrain from the splines: fairway, green,
   tee, rough, bunker sand, cart path. The fairways were detected from the actual
   mown grass, so they follow the real lanes — tweak any edge you don't like.
4. **Greens (19), tees (20), bunkers (69)** came straight from OSM and should sit
   right; the **14 fairways** OSM lacked were detected from the aerial.

---

## 5. Water — creek + ponds

`derived/water.geojson` has the 2 ponds and **Green Hills Creek** (buffered to a
~4 m channel). In Blender/OPCD:

- Cut the ponds in as water bodies (holes 13/14/16 area).
- The creek runs through the lower/SE holes. If the app shows on-course water on
  a hole the geojson misses, it's a drainage ditch not in OSM — trace it on the
  aerial and re-run, or add it by hand here.

---

## 6. Vegetation — Arborist (12,409 trees)

`derived/trees.csv` columns: `x_utm, y_utm, lon, lat, height_m, crown_radius_m, bucket`.

- Buckets: **tall (≥15 m), mid (6–15 m), shrub (2.5–6 m)** — map each to an
  Arborist tree model (e.g. tall→mature pine/eucalyptus, mid→broadleaf, shrub→bush).
- Trees were detected from the LIDAR canopy, so positions/heights/crowns are real
  and buildings were masked out (no trees on rooftops). Trees on the new black-tee
  pads were already pruned.
- Import the points into Arborist **(confirm Arborist's import format; if it wants
  local Unity X/Z, convert: `X = x_utm − xmin`, `Z = y_utm − ymin`, where xmin/ymin
  are the terrain-origin UTM corner — see `terrain_meta.json` + `build_layout` bbox)**.
- These are the corridor trees that make Green Hills tight; thin/fatten to taste.

---

## 7. Buildings + clubhouse

`derived/buildings.geojson` — 3,534 footprints with `height_m`, `levels`, and a
`kind` flag (`clubhouse` = the ~2,178 m² / 8.3 m building inside the boundary).

- Place the **clubhouse** model at its footprint/orientation, scaled to ~8 m.
- For the neighborhood skyline, drop simple house blocks at the in-course-adjacent
  footprints at their heights (median ~5 m). Distant rows can be billboards/low-poly.

---

## 8. Scenery & the views (the Green Hills feel)

`derived/viewshed.json` tells you what each hole sees:

- **Holes 5, 16, 18 play straight at SFO + the bay** — these are the hero views.
  Build the distant **SFO** (runways/terminals) and **bay** into the skybox /
  distant mesh in those sightlines. SFO is ~3.2 km NE, beyond the 2048 m terrain,
  so it's backdrop, not in-box geometry.
- Holes 1/3/7/8/14/15 also see the bay/airport.
- **Downtown SF is hidden behind San Bruno Mtn** — don't bother rendering it.
- Orient the **skybox to true north** so the sun and the SFO/bay bearings match
  reality. A photo-real option: shoot 360° panoramas from the hero tees and use
  them as the skybox behind those holes.

---

## 9. GreenKeeper (scorecard + tees + pins)

From `derived/course_data.json`, per hole:

- **Par / handicap / yardage** — Black/Blue Combo 6,428 / par 71 / 72.2 / 143.
- **Tee markers**: `tee_forward_latlon` (OSM tee) and, for holes **2/5/6/17/18**,
  `tee_black_latlon` (the championship tee you positioned). Other tee sets can be
  added later.
- **Pins**: `green_center_latlon` per hole.
- Set hole routing/order 1→18 and the tee/pin/flag locations in GreenKeeper.

> Hole 6 measures ~36 yd long from the placed tee vs the card — likely the green
> centroid; nudge the pin/green when you fine-tune and it cleans up.

---

## 10. Test, iterate, publish

1. Load the course in GSPro and play-test each hole. Use the per-hole crops
   (`preview/holes/`, regenerate with `hole_crops.py`) and your GPS-app shots as a
   hole-by-hole checklist.
2. Fix surfaces/trees/elevations that read wrong.
3. Publish through the OPCD/SGT submission flow when you're happy **(confirm the
   current submission steps)**.

---

## Rebuilding the data

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_all.py green-hills        # full pipeline
.venv/bin/python scripts/build_all.py green-hills --crops  # + per-hole crops
```

Edit `config/green-hills.yaml` (capture box, tree params) or
`config/green-hills-black-tees.yaml` (exact tee coords) and re-run.

To build a **different** course: copy `config/green-hills.yaml`, change the name/
center/scorecard, and run `build_all.py <slug>`.
