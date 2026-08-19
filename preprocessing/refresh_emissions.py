#!/usr/bin/env python3
"""Rebuild data/paris/emissions.json from Open Data Paris (24h complete)."""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "paris"
sys.path.insert(0, str(ROOT / "preprocessing"))

from build_data import (  # noqa: E402
    build_arc_hourly,
    build_emissions,
    centroid,
    citywide_profile,
    http_json,
    line_length_km,
)


def fetch_traffic_day(day: str):
    rows = []
    for h in range(24):
        if h < 23:
            where_clause = f"t_1h >= '{day}T{h:02d}:00:00' AND t_1h < '{day}T{h + 1:02d}:00:00'"
        else:
            where_clause = f"t_1h >= '{day}T23:00:00' AND t_1h <= '{day}T23:59:59'"
        where = urllib.parse.quote(where_clause)
        for start in range(0, 10000, 100):
            url = (
                "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
                f"comptages-routiers-permanents/records?limit=100&offset={start}"
                f"&where={where}&order_by=t_1h"
            )
            try:
                batch = http_json(url)["results"]
            except Exception as exc:
                print(f"h{h:02d} offset {start}: {exc}")
                break
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < 100:
                break
        if h % 6 == 0:
            print(f"  records: {len(rows)} (h{h:02d})")
    print(f"  records: {len(rows)} (complete)")
    return rows


def load_arcs_with_traffic(arc_hourly):
    ref = json.loads((DATA / "ref_raw.geojson").read_text(encoding="utf-8"))
    arcs = []
    for feat in ref["features"]:
        geom = feat.get("geometry") or {}
        if geom.get("type") != "LineString":
            continue
        coords = geom["coordinates"]
        if len(coords) < 2:
            continue
        props = feat["properties"]
        lon, lat = centroid(coords)
        if not (2.18 <= lon <= 2.48 and 48.78 <= lat <= 48.96):
            continue
        iu = str(props["iu_ac"])
        if not arc_hourly.get(iu) or sum(arc_hourly[iu]) == 0:
            continue
        arcs.append(
            {
                "iu_ac": iu,
                "name": props.get("libelle") or iu,
                "coords": [[c[0], c[1]] for c in coords],
                "lon": lon,
                "lat": lat,
                "length_km": line_length_km(coords),
            }
        )
    return arcs


def main():
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    day = manifest["traffic_day"]
    print(f"Fetching {day}…")
    rows = fetch_traffic_day(day)
    arc_hourly = build_arc_hourly(rows)
    city_profile = citywide_profile(arc_hourly)
    arcs = load_arcs_with_traffic(arc_hourly)
    emissions = build_emissions(arcs, arc_hourly, city_profile)
    (DATA / "emissions.json").write_text(json.dumps(emissions), encoding="utf-8")
    manifest["emission_points"] = len(emissions)
    manifest["traffic_records"] = len(rows)
    (DATA / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(emissions)} emission points")


if __name__ == "__main__":
    main()
