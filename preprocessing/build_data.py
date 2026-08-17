#!/usr/bin/env python3
"""Build Paris Carbon Clock datasets from open sources.

Sources:
  - Paris Open Data: referentiel-comptages-routiers + comptages-routiers-permanents
  - Open-Meteo CAMS air quality (PM2.5, NO2) at multiple Paris points
  - ADEME / EPA-style fleet CO2 factor for passenger cars (approx.)

Outputs under data/:
  emissions.json, airquality.json, trips.json, arcs.json, manifest.json
"""

from __future__ import annotations

import json
import math
import random
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "paris"
DATA.mkdir(exist_ok=True)

# g CO2 / km — approximate mixed urban fleet (ADEME ordre de grandeur VP)
CO2_G_PER_KM = 150.0
# assume each counted vehicle represents ~0.35 km of the arc contribution
ARC_KM_FACTOR = 0.35

PARIS_AQ_SITES = [
    {"id": "centre", "name": "Paris centre · Hôtel de Ville", "lat": 48.8566, "lng": 2.3522},
    {"id": "champs", "name": "Champs-Élysées", "lat": 48.8698, "lng": 2.3078},
    {"id": "opera", "name": "Opéra", "lat": 48.8719, "lng": 2.3316},
    {"id": "bastille", "name": "Bastille", "lat": 48.8532, "lng": 2.3691},
    {"id": "montparnasse", "name": "Montparnasse", "lat": 48.8421, "lng": 2.3219},
    {"id": "nation", "name": "Nation", "lat": 48.8484, "lng": 2.3959},
    {"id": "republique", "name": "République", "lat": 48.8676, "lng": 2.3631},
    {"id": "gare_lyon", "name": "Gare de Lyon", "lat": 48.8443, "lng": 2.3744},
    {"id": "saint_lazare", "name": "Saint-Lazare", "lat": 48.8765, "lng": 2.3255},
    {"id": "belleville", "name": "Belleville", "lat": 48.8724, "lng": 2.3820},
    {"id": "auteuil", "name": "Porte d'Auteuil", "lat": 48.8478, "lng": 2.2586},
    {"id": "italie", "name": "Place d'Italie", "lat": 48.8312, "lng": 2.3556},
    {"id": "clichy", "name": "Porte de Clichy", "lat": 48.8945, "lng": 2.3140},
    {"id": "vincennes", "name": "Porte de Vincennes", "lat": 48.8470, "lng": 2.4110},
    {"id": "orleans", "name": "Porte d'Orléans", "lat": 48.8230, "lng": 2.3255},
    {"id": "chapelle", "name": "Porte de la Chapelle", "lat": 48.8985, "lng": 2.3592},
]


def http_json(url: str, timeout: int = 90):
    req = urllib.request.Request(url, headers={"User-Agent": "carbon-clock-paris/1.0"})
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
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (sum(lons) / len(lons), sum(lats) / len(lats))


def normalize(values):
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def fetch_newest_day() -> str:
    url = (
        "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
        "comptages-routiers-permanents/records?limit=1&order_by=t_1h%20desc"
    )
    newest = http_json(url)["results"][0]["t_1h"]
    # Prefer the previous complete UTC day (rolling feed is often partial for "today")
    from datetime import date, timedelta

    d = date.fromisoformat(newest[:10]) - timedelta(days=1)
    return d.isoformat()


def fetch_traffic_day(day: str, max_records: int = 8000):
    rows = []
    where = urllib.parse.quote(f"t_1h >= '{day}T00:00:00' AND t_1h <= '{day}T23:59:59'")
    for start in range(0, max_records, 100):
        url = (
            "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
            f"comptages-routiers-permanents/records?limit=100&offset={start}"
            f"&where={where}&order_by=t_1h"
        )
        try:
            batch = http_json(url)["results"]
        except Exception as exc:
            print(f"traffic page {start} failed: {exc}")
            break
        if not batch:
            break
        rows.extend(batch)
        print(f"  traffic records: {len(rows)}")
        if len(batch) < 100:
            break
    return rows


def build_arc_hourly(rows):
    """iu_ac -> list[24] mean vehicle counts in Europe/Paris local hour."""
    buckets = defaultdict(lambda: defaultdict(list))
    for row in rows:
        q = row.get("q")
        if q is None:
            continue
        # Feed timestamps are UTC; shift to Paris civil hour for the clock UI
        ts = row["t_1h"].replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Approximate CEST (UTC+2) for summer POC; winter would be +1
        local_h = (dt.hour + 2) % 24
        buckets[str(row["iu_ac"])][local_h].append(float(q))

    out = {}
    for iu, hours in buckets.items():
        series = []
        for h in range(24):
            vals = hours.get(h)
            series.append(statistics.mean(vals) if vals else 0.0)
        out[iu] = series
    return out


def citywide_profile(arc_hourly: dict) -> list[float]:
    totals = [0.0] * 24
    counts = [0] * 24
    for series in arc_hourly.values():
        for h, v in enumerate(series):
            if v > 0:
                totals[h] += v
                counts[h] += 1
    means = [totals[h] / counts[h] if counts[h] else 0.0 for h in range(24)]
    # Typical Paris weekday shape used only to fill missing hours
    typical = [
        140, 95, 70, 55, 60, 140, 360, 560, 620, 580,
        520, 500, 530, 540, 550, 580, 640, 680, 600, 450,
        320, 250, 200, 160,
    ]
    known = [m for m in means if m > 0]
    scale = (statistics.mean(known) / statistics.mean(typical)) if known else 1.0
    filled = []
    for h in range(24):
        if means[h] > 0 and counts[h] >= max(3, int(0.01 * max(1, len(arc_hourly)))):
            filled.append(means[h])
        elif means[h] > 0:
            filled.append(0.6 * means[h] + 0.4 * typical[h] * scale)
        else:
            filled.append(typical[h] * scale)
    return filled


def load_referentiel(limit_arcs: int = 480):
    ref_path = DATA / "ref_raw.geojson"
    if not ref_path.exists():
        ref_path = DATA.parent / "ref_raw.geojson"
    ref = json.loads(ref_path.read_text(encoding="utf-8"))
    features = []
    for feat in ref["features"]:
        geom = feat.get("geometry") or {}
        if geom.get("type") != "LineString":
            continue
        coords = geom["coordinates"]
        if len(coords) < 2:
            continue
        props = feat["properties"]
        lon, lat = centroid(coords)
        # Paris + petite couronne (capteurs permanents Ville de Paris)
        if not (2.18 <= lon <= 2.48 and 48.78 <= lat <= 48.96):
            continue
        features.append(
            {
                "iu_ac": str(props["iu_ac"]),
                "name": props.get("libelle") or f"arc-{props['iu_ac']}",
                "coords": [[c[0], c[1]] for c in coords],
                "lon": lon,
                "lat": lat,
                "length_km": line_length_km(coords),
            }
        )

    # Spatial grid sample: couverture homogène, pas de cluster centre
    grid = 8
    min_lon, max_lon = 2.20, 2.46
    min_lat, max_lat = 48.80, 48.92
    cells = [[] for _ in range(grid * grid)]
    for a in features:
        gx = int(((a["lon"] - min_lon) / (max_lon - min_lon)) * grid)
        gy = int(((a["lat"] - min_lat) / (max_lat - min_lat)) * grid)
        gx = max(0, min(grid - 1, gx))
        gy = max(0, min(grid - 1, gy))
        cells[gy * grid + gx].append(a)
    for cell in cells:
        cell.sort(key=lambda a: -a["length_km"])
    picked = []
    while len(picked) < limit_arcs:
        added = False
        for cell in cells:
            if len(picked) >= limit_arcs:
                break
            if not cell:
                continue
            picked.append(cell.pop(0))
            added = True
        if not added:
            break
    return picked


def fetch_air_quality():
    stations = []
    # Prefer yesterday's completed day for a full 24h profile
    for site in PARIS_AQ_SITES:
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
            payload = http_json(url)
        except Exception as exc:
            print(f"AQ fail {site['id']}: {exc}")
            continue
        times = payload["hourly"]["time"]
        pm = payload["hourly"]["pm2_5"]
        no2 = payload["hourly"]["nitrogen_dioxide"]
        # Use the first complete local day in the series
        by_day = defaultdict(lambda: {"pm": [], "no2": [], "h": []})
        for t, p, n in zip(times, pm, no2):
            if p is None or n is None:
                continue
            day, hour = t[:10], int(t[11:13])
            by_day[day]["pm"].append((hour, p))
            by_day[day]["no2"].append((hour, n))
        # pick day with 24 hours if possible
        chosen = None
        for day, blk in sorted(by_day.items()):
            hours = {h for h, _ in blk["pm"]}
            if len(hours) >= 20:
                chosen = day
                break
        if not chosen:
            chosen = sorted(by_day.keys())[0]
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
        # intensity mostly from NO2 (traffic tracer) with PM blend
        intensity_raw = [0.65 * no224[h] + 0.35 * pm24[h] for h in range(24)]
        intensity = normalize(intensity_raw)
        stations.append(
            {
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
        )
        print(f"  AQ {site['id']} day={chosen}")
    return stations


def build_emissions(arcs, arc_hourly, city_profile):
    stations = []
    city_norm = normalize(city_profile)
    for arc in arcs:
        series = arc_hourly.get(arc["iu_ac"])
        if not series or sum(series) == 0:
            # Scale city profile by a pseudo capacity from length
            scale = 80 + 400 * min(arc["length_km"], 1.2)
            series = [city_norm[h] * scale for h in range(24)]
        # CO2 intensity proxy: vehicles * km * g/km -> normalize later per hour across city
        co2 = [q * max(arc["length_km"], ARC_KM_FACTOR) * CO2_G_PER_KM for q in series]
        intensity = normalize(co2)
        stations.append(
            {
                "id": arc["iu_ac"],
                "name": arc["name"],
                "lat": arc["lat"],
                "lng": arc["lon"],
                "hourly_volume": [round(v, 1) for v in series],
                "hourly_co2_g": [round(v, 1) for v in co2],
                "hourly_intensity": [round(v, 3) for v in intensity],
                "length_km": round(arc["length_km"], 3),
            }
        )
    return stations


def build_trips(arcs, arc_hourly, city_profile, n_trips: int = 12000):
    """Synthetic mobility trails along real Paris traffic arcs, weighted by hourly volume."""
    rng = random.Random(42)
    city_norm = normalize(city_profile)
    # Precompute per-arc weights
    weighted = []
    for arc in arcs:
        series = arc_hourly.get(arc["iu_ac"])
        mean_q = statistics.mean(series) if series and sum(series) > 0 else statistics.mean(city_profile)
        weighted.append((arc, max(mean_q, 1.0)))
    total_w = sum(w for _, w in weighted)

    trips = []
    for i in range(n_trips):
        r = rng.random() * total_w
        acc = 0.0
        arc = weighted[0][0]
        for a, w in weighted:
            acc += w
            if r <= acc:
                arc = a
                break
        coords = arc["coords"]
        # sample a subsegment
        if len(coords) >= 3:
            start = rng.randrange(0, len(coords) - 1)
            end = rng.randrange(start + 1, len(coords))
            path = coords[start : end + 1]
        else:
            path = coords
        # timestamp in seconds since midnight, biased to rush hours
        # inverse-CDF-ish using city profile
        h_weights = city_norm[:]
        s = sum(h_weights) or 1
        h_weights = [x / s for x in h_weights]
        x = rng.random()
        cum = 0.0
        hour = 0
        for h, w in enumerate(h_weights):
            cum += w
            if x <= cum:
                hour = h
                break
        t0 = hour * 3600 + rng.randint(0, 3599)
        # duration 3–18 minutes
        duration = rng.randint(180, 1080)
        timestamps = []
        path_out = []
        for j, pt in enumerate(path):
            frac = j / max(len(path) - 1, 1)
            timestamps.append(t0 + duration * frac)
            path_out.append([pt[0], pt[1]])
        trips.append(
            {
                "path": path_out,
                "timestamps": timestamps,
            }
        )
    return trips


def build_arcs_geo(arcs, arc_hourly, city_profile):
    city_norm = normalize(city_profile)
    features = []
    for arc in arcs:
        series = arc_hourly.get(arc["iu_ac"])
        if not series or sum(series) == 0:
            scale = 80 + 400 * min(arc["length_km"], 1.2)
            series = [city_norm[h] * scale for h in range(24)]
        intensity = normalize(series)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": arc["iu_ac"],
                    "name": arc["name"],
                    "hourly_volume": [round(v, 1) for v in series],
                    "hourly_intensity": [round(v, 3) for v in intensity],
                },
                "geometry": {"type": "LineString", "coordinates": arc["coords"]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def pearson(xs, ys):
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return 0.0
    return num / (denx * deny)


def main():
    import sys

    print("Loading referentiel…")
    arcs = load_referentiel(480)
    print(f"  selected arcs: {len(arcs)}")

    print("Fetching traffic day…")
    day = sys.argv[1] if len(sys.argv) > 1 else fetch_newest_day()
    print(f"  day: {day}")
    rows = fetch_traffic_day(day, max_records=12000)
    (DATA / "traffic_day_raw.json").write_text(
        json.dumps({"day": day, "count": len(rows)}, ensure_ascii=False),
        encoding="utf-8",
    )
    arc_hourly = build_arc_hourly(rows)
    print(f"  arcs with measurements: {len(arc_hourly)}")
    city_profile = citywide_profile(arc_hourly)
    print("  city hourly mean q:", [round(x, 1) for x in city_profile])

    print("Building emissions…")
    emissions = build_emissions(arcs, arc_hourly, city_profile)
    (DATA / "emissions.json").write_text(json.dumps(emissions), encoding="utf-8")

    print("Building traffic arcs geo…")
    arcs_geo = build_arcs_geo(arcs, arc_hourly, city_profile)
    (DATA / "arcs.json").write_text(json.dumps(arcs_geo), encoding="utf-8")

    print("Building trips…")
    trips = build_trips(arcs, arc_hourly, city_profile, n_trips=14000)
    (DATA / "trips.json").write_text(json.dumps(trips), encoding="utf-8")

    print("Fetching air quality (Open-Meteo CAMS)…")
    air = fetch_air_quality()
    (DATA / "airquality.json").write_text(json.dumps(air), encoding="utf-8")

    # Correlation: city traffic vs mean NO2 across stations
    if air:
        mean_no2 = [
            statistics.mean(st["hourly_no2"][h] for st in air) for h in range(24)
        ]
        corr = pearson(city_profile, mean_no2)
    else:
        mean_no2 = [0] * 24
        corr = 0.0

    manifest = {
        "title": "Carbon Clock — Paris",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "traffic_day": day,
        "traffic_records": len(rows),
        "arcs": len(arcs),
        "trips": len(trips),
        "air_stations": len(air),
        "correlation_traffic_no2": round(corr, 3),
        "sources": [
            {
                "layer": "Trafic / émissions",
                "name": "Comptages routiers permanents + référentiel",
                "publisher": "Ville de Paris / Open Data Paris",
                "url": "https://opendata.paris.fr/explore/dataset/comptages-routiers-permanents/",
            },
            {
                "layer": "Qualité de l'air",
                "name": "CAMS via Open-Meteo (PM2.5, NO2)",
                "publisher": "Open-Meteo / Copernicus CAMS",
                "url": "https://open-meteo.com/en/docs/air-quality-api",
            },
            {
                "layer": "Trajets (synthétiques)",
                "name": "Flux dérivés des arcs de comptage réels",
                "publisher": "POC carbon-clock-paris",
                "url": "",
            },
        ],
        "notes": [
            "Les trajets sont synthétiques, ancrés sur la géométrie réelle des arcs de comptage.",
            "Les émissions CO₂ sont une proxy (volume × longueur × facteur flotte urbaine).",
            f"Corrélation horaire trafic ↔ NO2 moyen: r={corr:.3f}",
        ],
        "hourly_traffic_mean": [round(x, 1) for x in city_profile],
        "hourly_no2_mean": [round(x, 2) for x in mean_no2],
    }
    (DATA / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Done.")
    print(json.dumps({k: manifest[k] for k in ("traffic_day", "arcs", "trips", "air_stations", "correlation_traffic_no2")}, indent=2))


if __name__ == "__main__":
    main()
