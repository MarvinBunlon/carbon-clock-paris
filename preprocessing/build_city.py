"""Build Carbon Clock dataset for Lyon or Marseille (OSM roads + Open-Meteo CAMS).

Paris uses the dedicated Open Data pipeline (build_data.py + extend_region.py).

Run from repo root:
  python preprocessing/build_city.py lyon
  python preprocessing/build_city.py marseille
"""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

DEFAULT_TRAFFIC = [
    71.8, 48.7, 302.8, 211.4, 156.0, 115.8, 184.5, 287.1, 317.8, 297.3,
    266.6, 256.3, 271.7, 276.8, 281.9, 297.3, 328.1, 348.6, 307.6, 230.7,
    164.0, 128.2, 102.5, 82.0,
]


def load_paris_traffic_profile():
    manifest_path = DATA / "paris" / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        profile = manifest.get("hourly_traffic_mean")
        if profile and len(profile) == 24:
            return profile
    return DEFAULT_TRAFFIC

CITY_SPECS = {
    "lyon": {
        "title": "Carbon Clock — Lyon",
        "region_label": "Métropole de Lyon",
        "bbox": (4.65, 45.68, 5.05, 45.85),
        "core": (4.836, 45.758),
        "timezone": "Europe/Paris",
        "osm_limit": 850,
        "trip_count": 11000,
        "aq_sites": [
            {"id": "bellecour", "name": "Lyon · Bellecour", "lat": 45.758, "lng": 4.835},
            {"id": "part_dieu", "name": "Part-Dieu", "lat": 45.760, "lng": 4.859},
            {"id": "vieux_lyon", "name": "Vieux Lyon", "lat": 45.762, "lng": 4.827},
            {"id": "confluence", "name": "Confluence", "lat": 45.741, "lng": 4.818},
            {"id": "gerland", "name": "Gerland", "lat": 45.727, "lng": 4.829},
            {"id": "vaise", "name": "Vaise", "lat": 45.775, "lng": 4.805},
            {"id": "croix_rousse", "name": "Croix-Rousse", "lat": 45.776, "lng": 4.832},
            {"id": "guillotiere", "name": "Guillotière", "lat": 45.753, "lng": 4.845},
            {"id": "villeurbanne", "name": "Villeurbanne", "lat": 45.767, "lng": 4.879},
            {"id": "venissieux", "name": "Vénissieux", "lat": 45.697, "lng": 4.885},
            {"id": "caluire", "name": "Caluire-et-Cuire", "lat": 45.795, "lng": 4.851},
            {"id": "bron", "name": "Bron", "lat": 45.738, "lng": 4.914},
            {"id": "oullins", "name": "Oullins", "lat": 45.715, "lng": 4.808},
            {"id": "ecully", "name": "Écully", "lat": 45.775, "lng": 4.778},
            {"id": "tassin", "name": "Tassin-la-Demi-Lune", "lat": 45.764, "lng": 4.778},
            {"id": "saint_priest", "name": "Saint-Priest", "lat": 45.696, "lng": 4.944},
            {"id": "meyzieu", "name": "Meyzieu", "lat": 45.767, "lng": 5.002},
            {"id": "decines", "name": "Décines-Charpieu", "lat": 45.769, "lng": 4.958},
            {"id": "rillieux", "name": "Rillieux-la-Pape", "lat": 45.822, "lng": 4.898},
            {"id": "vaulx", "name": "Vaulx-en-Velin", "lat": 45.779, "lng": 4.922},
            {"id": "saint_genis", "name": "Saint-Genis-Laval", "lat": 45.695, "lng": 4.793},
            {"id": "irigny", "name": "Irigny", "lat": 45.673, "lng": 4.821},
            {"id": "dardilly", "name": "Dardilly", "lat": 45.805, "lng": 4.753},
            {"id": "saint_fons", "name": "Saint-Fons", "lat": 45.707, "lng": 4.855},
            {"id": "pierre_benite", "name": "Pierre-Bénite", "lat": 45.705, "lng": 4.826},
        ],
    },
    "marseille": {
        "title": "Carbon Clock — Marseille",
        "region_label": "Métropole Aix-Marseille",
        "bbox": (5.12, 43.17, 5.58, 43.42),
        "core": (5.369, 43.296),
        "timezone": "Europe/Paris",
        "osm_limit": 850,
        "trip_count": 11000,
        "aq_sites": [
            {"id": "vieux_port", "name": "Marseille · Vieux-Port", "lat": 43.296, "lng": 5.369},
            {"id": "joliette", "name": "Joliette", "lat": 43.307, "lng": 5.367},
            {"id": "castellane", "name": "Castellane", "lat": 43.285, "lng": 5.382},
            {"id": "prado", "name": "Prado", "lat": 43.272, "lng": 5.385},
            {"id": "saint_charles", "name": "Saint-Charles", "lat": 43.303, "lng": 5.380},
            {"id": "endoume", "name": "Endoume", "lat": 43.280, "lng": 5.352},
            {"id": "la_timone", "name": "La Timone", "lat": 43.292, "lng": 5.400},
            {"id": "saint_barnabe", "name": "Saint-Barnabé", "lat": 43.302, "lng": 5.428},
            {"id": "bonneveine", "name": "Bonneveine", "lat": 43.255, "lng": 5.395},
            {"id": "l_estaque", "name": "L'Estaque", "lat": 43.361, "lng": 5.315},
            {"id": "aubagne", "name": "Aubagne", "lat": 43.293, "lng": 5.570},
            {"id": "allauch", "name": "Allauch", "lat": 43.336, "lng": 5.482},
            {"id": "plan_cuques", "name": "Plan-de-Cuques", "lat": 43.339, "lng": 5.446},
            {"id": "marignane", "name": "Marignane", "lat": 43.417, "lng": 5.214},
            {"id": "vitrolles", "name": "Vitrolles", "lat": 43.440, "lng": 5.248},
            {"id": "cabries", "name": "Cabries", "lat": 43.441, "lng": 5.380},
            {"id": "septemes", "name": "Septèmes-les-Vallons", "lat": 43.398, "lng": 5.365},
            {"id": "les_pennes", "name": "Les Pennes-Mirabeau", "lat": 43.410, "lng": 5.307},
            {"id": "la_ciotat", "name": "La Ciotat", "lat": 43.175, "lng": 5.608},
            {"id": "carnoux", "name": "Carnoux-en-Provence", "lat": 43.256, "lng": 5.564},
            {"id": "gignac", "name": "Gignac-la-Nerthe", "lat": 43.393, "lng": 5.234},
            {"id": "rognac", "name": "Rognac", "lat": 43.487, "lng": 5.238},
            {"id": "gardanne", "name": "Gardanne", "lat": 43.454, "lng": 5.469},
            {"id": "trets", "name": "Trets", "lat": 43.448, "lng": 5.681},
            {"id": "cassis", "name": "Cassis", "lat": 43.215, "lng": 5.538},
        ],
    },
}


def http_json(url: str, data: bytes | None = None, timeout: int = 120):
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "carbon-clock-paris/build-city-1.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
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


def pearson(a, b):
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    a, b = a[:n], b[:n]
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((x - mb) ** 2 for x in b))
    return num / (da * db) if da and db else 0.0


def fetch_osm_roads(bbox, core, limit: int):
    min_lon, min_lat, max_lon, max_lat = bbox
    query = f"""
    [out:json][timeout:90];
    (
      way["highway"="motorway"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"="motorway_link"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"="trunk"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"="primary"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"="secondary"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out geom qt;
    """
    print("Fetching OSM roads (Overpass)...")
    try:
        payload = http_json(
            "https://overpass-api.de/api/interpreter",
            data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
            timeout=120,
        )
    except Exception as exc:
        print(f"  Overpass failed: {exc}, trying mirror...")
        payload = http_json(
            "https://overpass.kumi.systems/api/interpreter",
            data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
            timeout=120,
        )

    arcs = []
    for el in payload.get("elements") or []:
        geom = el.get("geometry") or []
        if len(geom) < 2:
            continue
        coords = [[float(p["lon"]), float(p["lat"])] for p in geom]
        if len(coords) > 40:
            step = max(1, len(coords) // 30)
            coords = coords[::step]
            if coords[-1] != [geom[-1]["lon"], geom[-1]["lat"]]:
                coords.append([float(geom[-1]["lon"]), float(geom[-1]["lat"])])
        lon, lat = centroid(coords)
        dist = haversine_km((lon, lat), core)
        hwy = (el.get("tags") or {}).get("highway", "road")
        name = (el.get("tags") or {}).get("name") or (el.get("tags") or {}).get("ref") or f"osm-{el.get('id')}"
        weight = {
            "motorway": 1.0,
            "motorway_link": 0.75,
            "trunk": 0.9,
            "primary": 0.65,
            "secondary": 0.45,
        }.get(hwy, 0.35)
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
            }
        )

    arcs.sort(key=lambda a: (-a["weight"] * a["length_km"] * (0.5 + min(a["dist_km"], 15) / 15),))
    grid = 12
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
    while len(picked) < limit:
        added = False
        for cell in cells:
            if len(picked) >= limit:
                break
            if not cell:
                continue
            picked.append(cell.pop(0))
            added = True
        if not added:
            break
    print(f"  selected {len(picked)} arcs")
    return picked


def fetch_aq_point(site, timezone: str):
    url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality?"
        + urllib.parse.urlencode(
            {
                "latitude": site["lat"],
                "longitude": site["lng"],
                "hourly": "pm2_5,nitrogen_dioxide",
                "past_days": 2,
                "forecast_days": 0,
                "timezone": timezone,
            }
        )
    )
    try:
        payload = http_json(url, timeout=45)
    except Exception as exc:
        print(f"  AQ fail {site['id']}: {exc}")
        return None

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


def classify_aq_region(site, core):
    d = haversine_km((site["lng"], site["lat"]), core)
    if d <= 3.5:
        return "centre"
    if d <= 12:
        return "banlieue"
    return "grande_couronne"


def build_arc_feature(arc, city_norm):
    scale = 0.55 + 0.55 * arc["weight"]
    d = arc["dist_km"]
    ring = 1.0 + (0.2 if 2.5 <= d <= 10 else 0.0)
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


def build_emission(arc, city_norm):
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


def build_trips(arcs, city_norm, n_trips: int):
    rng = random.Random(42)
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
        h_weights = normalize(city_norm[:])
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


def build_city(city_id: str):
    spec = CITY_SPECS[city_id]
    bbox = spec["bbox"]
    core = spec["core"]
    out_dir = DATA / city_id
    out_dir.mkdir(parents=True, exist_ok=True)

    city_norm = normalize(load_paris_traffic_profile())
    traffic_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    arcs_raw = fetch_osm_roads(bbox, core, spec["osm_limit"])
    features = [build_arc_feature(a, city_norm) for a in arcs_raw]
    emissions = [build_emission(a, city_norm) for a in arcs_raw]
    trips = build_trips(arcs_raw, city_norm, spec["trip_count"])

    print(f"Fetching {len(spec['aq_sites'])} air stations (CAMS)...")
    air = []
    for site in spec["aq_sites"]:
        st = fetch_aq_point(site, spec["timezone"])
        if st:
            st["region"] = classify_aq_region(site, core)
            air.append(st)
            print(f"  ok {site['id']} ({st['region']})")

    no2_mean = []
    if air:
        for h in range(24):
            no2_mean.append(statistics.mean(st["hourly_no2"][h] for st in air))

    corr_all = pearson(load_paris_traffic_profile(), no2_mean) if no2_mean else 0.0
    corr_am = pearson(load_paris_traffic_profile()[6:10], no2_mean[6:10]) if no2_mean else 0.0
    corr_pm = pearson(load_paris_traffic_profile()[16:20], no2_mean[16:20]) if no2_mean else 0.0

    manifest = {
        "title": spec["title"],
        "city": city_id,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "traffic_day": traffic_day,
        "traffic_records": 0,
        "arcs": len(features),
        "trips": len(trips),
        "air_stations": len(air),
        "correlation_traffic_no2": round(corr_am, 3),
        "correlation_traffic_no2_all_day": round(corr_all, 3),
        "correlation_traffic_no2_morning_rush": round(corr_am, 3),
        "correlation_traffic_no2_evening_rush": round(corr_pm, 3),
        "hourly_traffic_mean": load_paris_traffic_profile(),
        "hourly_no2_mean": [round(x, 2) for x in no2_mean] if no2_mean else [],
        "sources": [
            {
                "layer": "Trafic / émissions",
                "name": "Axes OSM (motorway, trunk, primary, secondary)",
                "publisher": "OpenStreetMap via Overpass",
                "url": "https://www.openstreetmap.org",
            },
            {
                "layer": "Qualité de l'air",
                "name": "CAMS via Open-Meteo (PM2.5, NO2)",
                "publisher": "Open-Meteo / Copernicus CAMS",
                "url": "https://open-meteo.com/en/docs/air-quality-api",
            },
            {
                "layer": "Trajets (synthétiques)",
                "name": "Flux dérivés des axes OSM",
                "publisher": "POC carbon-clock-paris",
                "url": "",
            },
        ],
        "notes": [
            "Profil horaire trafic : journée type urbaine (proxy, pas de comptages locaux).",
            "Les émissions CO2 sont une proxy (volume x longueur x facteur flotte urbaine).",
            f"Correlation 24h trafic-NO2: r={corr_all:.3f}.",
            f"Correlation pointe matin 6-10h: r={corr_am:.3f}.",
            f"Correlation pointe soir 16-20h: r={corr_pm:.3f}.",
            f"Qualité de l'air : {len(air)} points CAMS nommés ({spec['region_label']}).",
        ],
        "region": {
            "label": spec["region_label"],
            "bbox": list(bbox),
            "city_arcs": 0,
            "regional_arcs_osm": len(features),
            "sources_extra": ["OpenStreetMap Overpass API"],
        },
    }

    (out_dir / "arcs.json").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
    )
    (out_dir / "emissions.json").write_text(json.dumps(emissions), encoding="utf-8")
    (out_dir / "trips.json").write_text(json.dumps(trips), encoding="utf-8")
    (out_dir / "airquality.json").write_text(json.dumps(air), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Done {city_id}: arcs={len(features)} trips={len(trips)} air={len(air)}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CITY_SPECS:
        print("Usage: python preprocessing/build_city.py [lyon|marseille]")
        sys.exit(1)
    build_city(sys.argv[1])


if __name__ == "__main__":
    main()
