"""Extend Carbon Clock coverage to petite couronne / heart of Île-de-France.

Paris Open Data sensors stop at the périphérique. This script:
  - keeps existing Paris arcs/emissions profiles
  - fetches OSM motorway/trunk/primary ways for a wider bbox (Overpass)
  - builds synthetic hourly intensities from the Paris city profile
  - adds regional air-quality sample points (Open-Meteo or nearest-station proxy)
  - widens trips + updates manifest

Run from repo root:
  python preprocessing/extend_region.py
"""

from __future__ import annotations

import json
import math
import random
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "paris"

# Heart of Île-de-France (petite couronne + portes)
REGION_BBOX = (2.05, 48.72, 2.62, 49.02)  # min_lon, min_lat, max_lon, max_lat
PARIS_CORE = (2.3522, 48.8566)

REGION_AQ_SITES = [
    {"id": "nanterre", "name": "Nanterre", "lat": 48.892, "lng": 2.207},
    {"id": "la_defense", "name": "La Défense", "lat": 48.891, "lng": 2.240},
    {"id": "boulogne", "name": "Boulogne-Billancourt", "lat": 48.835, "lng": 2.241},
    {"id": "issy", "name": "Issy-les-Moulineaux", "lat": 48.824, "lng": 2.273},
    {"id": "saint_denis", "name": "Saint-Denis · Stade de France", "lat": 48.924, "lng": 2.360},
    {"id": "aubervilliers", "name": "Aubervilliers", "lat": 48.913, "lng": 2.383},
    {"id": "pantin", "name": "Pantin", "lat": 48.894, "lng": 2.408},
    {"id": "montreuil", "name": "Montreuil", "lat": 48.863, "lng": 2.443},
    {"id": "vincennes_bois", "name": "Vincennes", "lat": 48.847, "lng": 2.438},
    {"id": "creteil", "name": "Créteil", "lat": 48.790, "lng": 2.455},
    {"id": "vitry", "name": "Vitry-sur-Seine", "lat": 48.787, "lng": 2.403},
    {"id": "ivry", "name": "Ivry-sur-Seine", "lat": 48.813, "lng": 2.385},
    {"id": "villejuif", "name": "Villejuif", "lat": 48.792, "lng": 2.363},
    {"id": "arcueil", "name": "Arcueil / Bagneux", "lat": 48.808, "lng": 2.333},
    {"id": "clamart", "name": "Clamart", "lat": 48.801, "lng": 2.263},
    {"id": "courbevoie", "name": "Courbevoie", "lat": 48.897, "lng": 2.253},
    {"id": "levallois", "name": "Levallois-Perret", "lat": 48.893, "lng": 2.288},
    {"id": "saint_ouen", "name": "Saint-Ouen", "lat": 48.912, "lng": 2.334},
    {"id": "argenteuil", "name": "Argenteuil", "lat": 48.948, "lng": 2.245},
    {"id": "versailles", "name": "Versailles", "lat": 48.805, "lng": 2.130},
]


def http_json(url: str, data: bytes | None = None, timeout: int = 120):
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "carbon-clock-paris/region-1.0", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def haversine_km(a, b) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def line_length_km(coords) -> float:
    total = 0.0
    for i in range(1, len(coords)):
        total += haversine_km(coords[i - 1], coords[i])
    return max(total, 0.05)


def centroid(coords):
    return (
        sum(c[0] for c in coords) / len(coords),
        sum(c[1] for c in coords) / len(coords),
    )


def normalize(xs):
    mx = max(xs) if xs else 1.0
    if mx <= 0:
        return [0.0] * len(xs)
    return [x / mx for x in xs]


def fetch_osm_major_roads(limit_ways: int = 700):
    min_lon, min_lat, max_lon, max_lat = REGION_BBOX
    query = f"""
    [out:json][timeout:90];
    (
      way["highway"="motorway"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"="motorway_link"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"="trunk"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"="primary"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out geom qt;
    """
    print("Fetching OSM major roads (Overpass)…")
    try:
        payload = http_json(
            "https://overpass-api.de/api/interpreter",
            data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
            timeout=120,
        )
    except Exception as exc:
        print(f"  Overpass failed: {exc}")
        print("  Trying mirror…")
        payload = http_json(
            "https://overpass.kumi.systems/api/interpreter",
            data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
            timeout=120,
        )

    elements = payload.get("elements") or []
    print(f"  OSM ways: {len(elements)}")
    arcs = []
    for el in elements:
        geom = el.get("geometry") or []
        if len(geom) < 2:
            continue
        coords = [[float(p["lon"]), float(p["lat"])] for p in geom]
        # simplify: keep every Nth point for long ways
        if len(coords) > 40:
            step = max(1, len(coords) // 30)
            coords = coords[::step]
            if coords[-1] != [geom[-1]["lon"], geom[-1]["lat"]]:
                coords.append([float(geom[-1]["lon"]), float(geom[-1]["lat"])])
        lon, lat = centroid(coords)
        # Prefer outside intramuros to fill the region (Paris already covered)
        dist = haversine_km((lon, lat), PARIS_CORE)
        hwy = (el.get("tags") or {}).get("highway", "road")
        name = (el.get("tags") or {}).get("name") or (el.get("tags") or {}).get("ref") or f"osm-{el.get('id')}"
        weight = {"motorway": 1.0, "motorway_link": 0.7, "trunk": 0.85, "primary": 0.55}.get(hwy, 0.4)
        arcs.append(
            {
                "iu_ac": f"osm-{el.get('id')}",
                "name": name,
                "coords": coords,
                "lon": lon,
                "lat": lat,
                "length_km": line_length_km(coords),
                "highway": hwy,
                "weight": weight,
                "dist_km": dist,
                "synthetic": True,
            }
        )

    # Prefer longer / higher-class roads, spread spatially, favor banlieue
    arcs.sort(key=lambda a: (-a["weight"] * a["length_km"] * (0.6 + min(a["dist_km"], 12) / 12),))
    # Spatial grid pick
    grid = 10
    min_lon, min_lat, max_lon, max_lat = REGION_BBOX
    cells = [[] for _ in range(grid * grid)]
    for a in arcs:
        gx = int(((a["lon"] - min_lon) / (max_lon - min_lon)) * grid)
        gy = int(((a["lat"] - min_lat) / (max_lat - min_lat)) * grid)
        gx = max(0, min(grid - 1, gx))
        gy = max(0, min(grid - 1, gy))
        cells[gy * grid + gx].append(a)
    for cell in cells:
        cell.sort(key=lambda a: -a["weight"] * a["length_km"])
    picked = []
    while len(picked) < limit_ways:
        added = False
        for cell in cells:
            if len(picked) >= limit_ways:
                break
            if not cell:
                continue
            picked.append(cell.pop(0))
            added = True
        if not added:
            break
    print(f"  selected regional arcs: {len(picked)}")
    return picked


def fetch_aq_point(site, fallback_series=None):
    url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality?"
        + urllib.parse.urlencode(
            {
                "latitude": site["lat"],
                "longitude": site["lng"],
                "hourly": "pm2_5,nitrogen_dioxide",
                "past_days": 2,
                "forecast_days": 0,
                "timezone": "Europe/Paris",
            }
        )
    )
    try:
        payload = http_json(url, timeout=40)
    except Exception as exc:
        print(f"  AQ fail {site['id']}: {exc}")
        if not fallback_series:
            return None
        base = dict(fallback_series)
        base.update({"id": site["id"], "name": site["name"], "lat": site["lat"], "lng": site["lng"], "source": "proxy-nearest"})
        return base

    times = payload["hourly"]["time"]
    pm = payload["hourly"]["pm2_5"]
    no2 = payload["hourly"]["nitrogen_dioxide"]
    by_day = {}
    for t, p, n in zip(times, pm, no2):
        if p is None or n is None:
            continue
        day, hour = t[:10], int(t[11:13])
        by_day.setdefault(day, {"pm": [], "no2": []})
        by_day[day]["pm"].append((hour, p))
        by_day[day]["no2"].append((hour, n))
    if not by_day:
        return None
    chosen = sorted(by_day.keys())[-1]
    for day, blk in sorted(by_day.items()):
        if len({h for h, _ in blk["pm"]}) >= 20:
            chosen = day
            break
    pm24 = [0.0] * 24
    no224 = [0.0] * 24
    pmc = [0] * 24
    noc = [0] * 24
    for h, v in by_day[chosen]["pm"]:
        pm24[h] += v
        pmc[h] += 1
    for h, v in by_day[chosen]["no2"]:
        no224[h] += v
        noc[h] += 1
    pm24 = [pm24[h] / pmc[h] if pmc[h] else 0 for h in range(24)]
    no224 = [no224[h] / noc[h] if noc[h] else 0 for h in range(24)]
    intensity = normalize([0.65 * no224[h] + 0.35 * pm24[h] for h in range(24)])
    return {
        "id": site["id"],
        "name": site["name"],
        "lat": site["lat"],
        "lng": site["lng"],
        "pollutants": ["PM2.5", "NO2"],
        "hourly_pm25": [round(x, 2) for x in pm24],
        "hourly_no2": [round(x, 2) for x in no224],
        "hourly_intensity": [round(x, 3) for x in intensity],
        "source": "open-meteo-cams",
        "day": chosen,
    }


def build_synthetic_feature(arc, city_norm):
    # Banlieue slightly less intense overnight, strong on radial motorways
    scale = 0.55 + 0.55 * arc["weight"]
    # Soft ring boost near périphérique distance 4–9 km
    d = arc["dist_km"]
    ring = 1.0 + (0.25 if 3.5 <= d <= 10 else 0.0)
    series = [city_norm[h] * scale * ring for h in range(24)]
    intensity = normalize(series)
    return {
        "type": "Feature",
        "properties": {
            "id": arc["iu_ac"],
            "name": arc["name"],
            "hourly_volume": [round(v * 400, 1) for v in series],
            "hourly_intensity": [round(v, 3) for v in intensity],
            "synthetic": True,
            "highway": arc.get("highway"),
        },
        "geometry": {"type": "LineString", "coordinates": arc["coords"]},
    }


def build_emission_station(arc, city_norm):
    scale = 80 + 400 * min(arc["length_km"], 1.5) * arc["weight"]
    series = [city_norm[h] * scale for h in range(24)]
    co2 = [q * max(arc["length_km"], 0.35) * 150.0 for q in series]
    return {
        "id": arc["iu_ac"],
        "name": arc["name"],
        "lat": arc["lat"],
        "lng": arc["lon"],
        "hourly_volume": [round(v, 1) for v in series],
        "hourly_co2_g": [round(v, 1) for v in co2],
        "hourly_intensity": [round(v, 3) for v in normalize(co2)],
        "length_km": round(arc["length_km"], 3),
        "synthetic": True,
    }


def build_trips_for_arcs(arcs, city_norm, n_trips: int = 3500):
    rng = random.Random(7)
    weighted = [(a, max(a["weight"] * a["length_km"], 0.2)) for a in arcs]
    total_w = sum(w for _, w in weighted) or 1
    trips = []
    for _ in range(n_trips):
        r = rng.random() * total_w
        acc = 0.0
        arc = weighted[0][0]
        for a, w in weighted:
            acc += w
            if r <= acc:
                arc = a
                break
        coords = arc["coords"]
        if len(coords) >= 3:
            start = rng.randrange(0, len(coords) - 1)
            end = rng.randrange(start + 1, len(coords))
            path = coords[start : end + 1]
        else:
            path = coords
        # bias to rush via city profile
        h_weights = city_norm[:]
        s = sum(h_weights) or 1
        h_weights = [x / s for x in h_weights]
        u = rng.random()
        acc = 0.0
        hour = 0
        for h, w in enumerate(h_weights):
            acc += w
            if u <= acc:
                hour = h
                break
        t0 = hour * 3600 + rng.random() * 3600
        travel = 90 + rng.random() * 240
        n = len(path)
        timestamps = [t0 + travel * i / max(n - 1, 1) for i in range(n)]
        trips.append({"path": path, "timestamps": [round(x, 1) for x in timestamps]})
    return trips


def main():
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    city_raw = manifest.get("hourly_traffic_mean") or [100] * 24
    city_norm = normalize(city_raw)

    arcs_geo = json.loads((DATA / "arcs.json").read_text(encoding="utf-8"))
    emissions = json.loads((DATA / "emissions.json").read_text(encoding="utf-8"))
    air = json.loads((DATA / "airquality.json").read_text(encoding="utf-8"))
    trips = json.loads((DATA / "trips.json").read_text(encoding="utf-8"))

    existing_ids = {str(f["properties"]["id"]) for f in arcs_geo["features"]}
    print(f"Paris arcs already loaded: {len(existing_ids)}")

    regional = fetch_osm_major_roads(limit_ways=650)
    regional = [a for a in regional if a["iu_ac"] not in existing_ids]
    # Drop tiny stubs
    regional = [a for a in regional if a["length_km"] >= 0.25]
    print(f"Regional arcs to add: {len(regional)}")

    new_features = [build_synthetic_feature(a, city_norm) for a in regional]
    new_emissions = [build_emission_station(a, city_norm) for a in regional]
    new_trips = build_trips_for_arcs(regional, city_norm, n_trips=4000)

    arcs_geo["features"].extend(new_features)
    emissions.extend(new_emissions)
    trips.extend(new_trips)

    # Air quality: keep existing, add regional missing ids
    have = {st["id"] for st in air}
    fallback = air[0] if air else None
    print("Fetching regional air quality…")
    for site in REGION_AQ_SITES:
        if site["id"] in have:
            continue
        st = fetch_aq_point(site, fallback_series=fallback)
        if st:
            air.append(st)
            print(f"  + {site['id']}")

    (DATA / "arcs.json").write_text(json.dumps(arcs_geo), encoding="utf-8")
    (DATA / "emissions.json").write_text(json.dumps(emissions), encoding="utf-8")
    (DATA / "trips.json").write_text(json.dumps(trips), encoding="utf-8")
    (DATA / "airquality.json").write_text(json.dumps(air), encoding="utf-8")

    manifest["arcs"] = len(arcs_geo["features"])
    manifest["trips"] = len(trips)
    manifest["air_stations"] = len(air)
    manifest["built_at"] = datetime.now(timezone.utc).isoformat()
    manifest["region"] = {
        "label": "Paris + petite couronne (cœur Île-de-France)",
        "bbox": list(REGION_BBOX),
        "paris_arcs": len(existing_ids),
        "regional_arcs_osm": len(new_features),
        "sources_extra": [
            "OpenStreetMap major roads (motorway/trunk/primary) via Overpass — intensités synthétiques calées sur le profil Paris",
            "Open-Meteo CAMS air quality on regional sample points",
        ],
    }
    note = "Couverture étendue à la petite couronne via axes OSM + stations air régionales."
    notes = list(manifest.get("notes") or [])
    if note not in notes:
        notes.append(note)
    manifest["notes"] = notes
    (DATA / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # distribution check
    grid = 8
    min_lon, min_lat, max_lon, max_lat = REGION_BBOX
    cells = [0] * (grid * grid)
    for f in arcs_geo["features"]:
        cs = f["geometry"]["coordinates"]
        lon = sum(c[0] for c in cs) / len(cs)
        lat = sum(c[1] for c in cs) / len(cs)
        gx = max(0, min(grid - 1, int((lon - min_lon) / (max_lon - min_lon) * grid)))
        gy = max(0, min(grid - 1, int((lat - min_lat) / (max_lat - min_lat) * grid)))
        cells[gy * grid + gx] += 1
    print("region grid:")
    for y in range(grid - 1, -1, -1):
        print(" ".join(f"{cells[y * grid + x]:3d}" for x in range(grid)))
    print(f"Done. arcs={manifest['arcs']} air={manifest['air_stations']} trips={manifest['trips']}")


if __name__ == "__main__":
    main()
