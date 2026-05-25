"""Build a hole-by-hole report from OSM golf=hole centerlines + greens/tees."""
from gspro_course.geo import Projector, line_length_m, compass_bearing, compass_label

M_TO_YD = 1.09361


def _estimate_par(length_m: float) -> int:
    if length_m < 215:
        return 3
    if length_m < 430:
        return 4
    return 5


def build(features, cfg) -> dict:
    proj = Projector(cfg.epsg)
    holes = [f for f in features if f["category"] == "hole"]

    rows = []
    for h in holes:
        ll = list(h["geom"].coords)
        xy = proj.ring_xy(ll)
        length_m = line_length_m(xy)
        bearing = compass_bearing(xy[0], xy[-1])  # tee -> green
        t = h["tags"]
        ref = t.get("ref")
        try:
            ref_num = int(ref) if ref is not None else None
        except ValueError:
            ref_num = None
        par = int(t["par"]) if t.get("par", "").isdigit() else _estimate_par(length_m)
        rows.append({
            "ref": ref_num,
            "name": t.get("name"),
            "length_m": round(length_m, 1),
            "length_yd": round(length_m * M_TO_YD),
            "bearing_deg": round(bearing, 1),
            "facing": compass_label(bearing),
            "par": par,
            "par_source": "osm" if t.get("par", "").isdigit() else "estimated",
        })

    rows.sort(key=lambda r: (r["ref"] is None, r["ref"] if r["ref"] else 0))
    total_yd = sum(r["length_yd"] for r in rows)
    total_par = sum(r["par"] for r in rows)
    return {
        "course": cfg.name,
        "holes_found": len(rows),
        "total_yards": total_yd,
        "total_par": total_par,
        "holes": rows,
    }


def format_table(report: dict) -> str:
    lines = [
        f"{report['course']} — {report['holes_found']} holes mapped",
        f"Total: {report['total_yards']} yd, par {report['total_par']} "
        f"(par values: {'tagged' if all(h['par_source']=='osm' for h in report['holes']) else 'estimated from length'})",
        "",
        f"{'Hole':>4} {'Yards':>6} {'Par':>4} {'Faces':>6}  Bearing",
    ]
    for h in report["holes"]:
        ref = h["ref"] if h["ref"] is not None else "?"
        lines.append(
            f"{ref:>4} {h['length_yd']:>6} {h['par']:>4} {h['facing']:>6}  {h['bearing_deg']:>5.0f}deg"
        )
    return "\n".join(lines)
