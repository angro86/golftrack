"""Hole-by-hole report.

Uses the authoritative scorecard (par / handicap / yardage per tee set) when
present in the config, and overlays the play direction ("facing") derived from
the OSM golf=hole centerlines for the view-corridor analysis. Also reports the
OSM centerline length per hole as a geometry sanity check.
"""
from gspro_course.geo import Projector, line_length_m, compass_bearing, compass_label

M_TO_YD = 1.09361


def _estimate_par(length_m: float) -> int:
    if length_m < 215:
        return 3
    if length_m < 430:
        return 4
    return 5


def _osm_holes(features, cfg):
    """ref -> {bearing, facing, osm_yd} from OSM golf=hole centerlines."""
    proj = Projector(cfg.epsg)
    out = {}
    for f in features:
        if f["category"] != "hole":
            continue
        ll = list(f["geom"].coords)
        xy = proj.ring_xy(ll)
        bearing = compass_bearing(xy[0], xy[-1])
        ref = f["tags"].get("ref")
        try:
            ref = int(ref)
        except (TypeError, ValueError):
            ref = None
        out[ref] = {
            "bearing_deg": round(bearing, 1),
            "facing": compass_label(bearing),
            "osm_centerline_yd": round(line_length_m(xy) * M_TO_YD),
        }
    return out


def build(features, cfg) -> dict:
    osm = _osm_holes(features, cfg)
    sc = cfg.scorecard
    if not sc:
        return _build_from_osm(osm, cfg)

    tees = sc["tees"]
    par_by = sc["par_by_hole"]
    hcp_by = sc.get("hcp_by_hole", [None] * 18)
    rows = []
    for i in range(18):
        ref = i + 1
        o = osm.get(ref, {})
        rows.append({
            "ref": ref,
            "par": par_by[i],
            "hcp": hcp_by[i],
            "yards": {t["name"]: t["holes_yards"][i] for t in tees},
            "bearing_deg": o.get("bearing_deg"),
            "facing": o.get("facing"),
            "osm_centerline_yd": o.get("osm_centerline_yd"),
        })
    longest = max(tees, key=lambda t: t["yards"])
    return {
        "course": cfg.name,
        "scorecard_source": sc.get("source"),
        "holes_found": 18,
        "total_par": sum(par_by),
        "total_yards": longest["yards"],
        "tees": [{k: t.get(k) for k in ("name", "yards", "par", "rating", "slope")}
                 for t in tees],
        "holes": rows,
    }


def _build_from_osm(osm, cfg):
    rows = []
    for ref, o in sorted((r, v) for r, v in osm.items() if r is not None):
        yd = o["osm_centerline_yd"]
        rows.append({"ref": ref, "par": _estimate_par(yd / M_TO_YD),
                     "yards": {"osm_centerline": yd}, **o})
    return {
        "course": cfg.name,
        "scorecard_source": "OSM centerline (no scorecard configured)",
        "holes_found": len(rows),
        "total_par": sum(r["par"] for r in rows),
        "total_yards": sum(r["osm_centerline_yd"] for r in rows),
        "holes": rows,
    }


def format_table(report: dict) -> str:
    lines = [f"{report['course']} — {report['holes_found']} holes"]
    if report.get("tees"):
        for t in report["tees"]:
            lines.append(f"  {t['name']}: {t['yards']} yd, par {t['par']}, "
                         f"rating {t['rating']}, slope {t['slope']}")
    lines.append(f"  source: {report.get('scorecard_source')}")
    lines.append("")
    lines.append(f"{'Hole':>4} {'Par':>4} {'HCP':>4} {'Yds':>5} {'Faces':>6} {'OSMyd':>6}")
    for h in report["holes"]:
        yds = max(h["yards"].values()) if isinstance(h["yards"], dict) else h["yards"]
        lines.append(
            f"{h['ref']:>4} {h['par']:>4} {str(h.get('hcp','')):>4} {yds:>5} "
            f"{str(h.get('facing','')):>6} {str(h.get('osm_centerline_yd','')):>6}")
    return "\n".join(lines)
