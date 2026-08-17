"""Rebuild arcs/emissions/trips with spatial grid sampling (no network)."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_data import (  # noqa: E402
    DATA,
    build_arcs_geo,
    build_emissions,
    build_trips,
    load_referentiel,
)


def main():
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    city_profile = manifest["hourly_traffic_mean"]
    arcs = load_referentiel(480)
    print(f"selected {len(arcs)}")

    arc_hourly = {}
    emissions = build_emissions(arcs, arc_hourly, city_profile)
    arcs_geo = build_arcs_geo(arcs, arc_hourly, city_profile)
    trips = build_trips(arcs, arc_hourly, city_profile, n_trips=9000)

    (DATA / "emissions.json").write_text(json.dumps(emissions), encoding="utf-8")
    (DATA / "arcs.json").write_text(json.dumps(arcs_geo), encoding="utf-8")
    (DATA / "trips.json").write_text(json.dumps(trips), encoding="utf-8")

    manifest["arcs"] = len(arcs)
    manifest["trips"] = len(trips)
    manifest["built_at"] = datetime.now(timezone.utc).isoformat()
    note = "Axes rééchantillonnés en grille spatiale (couverture Paris + petite couronne)."
    notes = list(manifest.get("notes") or [])
    if note not in notes:
        notes.append(note)
    manifest["notes"] = notes
    (DATA / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    grid = 8
    min_lon, max_lon = 2.20, 2.46
    min_lat, max_lat = 48.80, 48.92
    cells = [0] * (grid * grid)
    for a in arcs:
        gx = max(0, min(grid - 1, int((a["lon"] - min_lon) / (max_lon - min_lon) * grid)))
        gy = max(0, min(grid - 1, int((a["lat"] - min_lat) / (max_lat - min_lat) * grid)))
        cells[gy * grid + gx] += 1
    print("grid:")
    for y in range(grid - 1, -1, -1):
        print(" ".join(f"{cells[y * grid + x]:3d}" for x in range(grid)))
    print("done")


if __name__ == "__main__":
    main()
