"""Refresh air-quality stations for Paris + petite & grande couronne (Open-Meteo CAMS).

Re-fetches all known named sites across the Île-de-France map extent.

Run from repo root:
  python preprocessing/refresh_air.py
"""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "paris"

REGION_BBOX = (2.05, 48.72, 2.62, 49.02)
PARIS_CORE = (2.3522, 48.8566)

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
    {"id": "belleville", "name": "Belleville", "lat": 48.8724, "lng": 2.382},
    {"id": "auteuil", "name": "Porte d'Auteuil", "lat": 48.8478, "lng": 2.2586},
    {"id": "italie", "name": "Place d'Italie", "lat": 48.8312, "lng": 2.3556},
    {"id": "clichy", "name": "Porte de Clichy", "lat": 48.8945, "lng": 2.314},
    {"id": "vincennes", "name": "Porte de Vincennes", "lat": 48.847, "lng": 2.411},
    {"id": "orleans", "name": "Porte d'Orléans", "lat": 48.823, "lng": 2.3255},
    {"id": "chapelle", "name": "Porte de la Chapelle", "lat": 48.8985, "lng": 2.3592},
]

REGION_AQ_SITES = [
    {"id": "nanterre", "name": "Nanterre", "lat": 48.892, "lng": 2.207},
    {"id": "la_defense", "name": "La Défense", "lat": 48.891, "lng": 2.24},
    {"id": "boulogne", "name": "Boulogne-Billancourt", "lat": 48.835, "lng": 2.241},
    {"id": "issy", "name": "Issy-les-Moulineaux", "lat": 48.824, "lng": 2.273},
    {"id": "saint_denis", "name": "Saint-Denis · Stade de France", "lat": 48.924, "lng": 2.36},
    {"id": "aubervilliers", "name": "Aubervilliers", "lat": 48.913, "lng": 2.383},
    {"id": "pantin", "name": "Pantin", "lat": 48.894, "lng": 2.408},
    {"id": "montreuil", "name": "Montreuil", "lat": 48.863, "lng": 2.443},
    {"id": "vincennes_bois", "name": "Vincennes", "lat": 48.847, "lng": 2.438},
    {"id": "creteil", "name": "Créteil", "lat": 48.79, "lng": 2.455},
    {"id": "vitry", "name": "Vitry-sur-Seine", "lat": 48.787, "lng": 2.403},
    {"id": "ivry", "name": "Ivry-sur-Seine", "lat": 48.813, "lng": 2.385},
    {"id": "villejuif", "name": "Villejuif", "lat": 48.792, "lng": 2.363},
    {"id": "arcueil", "name": "Arcueil / Bagneux", "lat": 48.808, "lng": 2.333},
    {"id": "clamart", "name": "Clamart", "lat": 48.801, "lng": 2.263},
    {"id": "courbevoie", "name": "Courbevoie", "lat": 48.897, "lng": 2.253},
    {"id": "levallois", "name": "Levallois-Perret", "lat": 48.893, "lng": 2.288},
    {"id": "saint_ouen", "name": "Saint-Ouen", "lat": 48.912, "lng": 2.334},
    {"id": "argenteuil", "name": "Argenteuil", "lat": 48.948, "lng": 2.245},
    {"id": "versailles", "name": "Versailles", "lat": 48.805, "lng": 2.13},
    {"id": "neuilly", "name": "Neuilly-sur-Seine", "lat": 48.884, "lng": 2.269},
    {"id": "suresnes", "name": "Suresnes", "lat": 48.871, "lng": 2.229},
    {"id": "colombes", "name": "Colombes", "lat": 48.923, "lng": 2.252},
    {"id": "drancy", "name": "Drancy", "lat": 48.925, "lng": 2.445},
    {"id": "bondy", "name": "Bondy", "lat": 48.901, "lng": 2.482},
    {"id": "choisy", "name": "Choisy-le-Roi", "lat": 48.768, "lng": 2.409},
    {"id": "saint_maur", "name": "Saint-Maur-des-Fossés", "lat": 48.799, "lng": 2.499},
    {"id": "meudon", "name": "Meudon", "lat": 48.813, "lng": 2.235},
]

# Grande couronne — bords nord / est / ouest / sud de la bbox carte
GRANDE_COURONNE_AQ_SITES = [
    {"id": "sarcelles", "name": "Sarcelles", "lat": 48.997, "lng": 2.378},
    {"id": "gonesse", "name": "Gonesse", "lat": 48.986, "lng": 2.452},
    {"id": "tremblay", "name": "Tremblay-en-France", "lat": 49.006, "lng": 2.569},
    {"id": "montmorency", "name": "Montmorency", "lat": 48.988, "lng": 2.322},
    {"id": "enghien", "name": "Enghien-les-Bains", "lat": 48.970, "lng": 2.308},
    {"id": "franconville", "name": "Franconville", "lat": 48.989, "lng": 2.227},
    {"id": "cormeilles", "name": "Cormeilles-en-Parisis", "lat": 48.974, "lng": 2.201},
    {"id": "les_mureaux", "name": "Les Mureaux", "lat": 48.991, "lng": 2.162},
    {"id": "poissy", "name": "Poissy", "lat": 48.929, "lng": 2.048},
    {"id": "saint_germain", "name": "Saint-Germain-en-Laye", "lat": 48.898, "lng": 2.094},
    {"id": "houilles", "name": "Houilles", "lat": 48.923, "lng": 2.189},
    {"id": "trappes", "name": "Trappes", "lat": 48.774, "lng": 2.058},
    {"id": "plaisir", "name": "Plaisir", "lat": 48.818, "lng": 2.062},
    {"id": "guyancourt", "name": "Guyancourt", "lat": 48.773, "lng": 2.074},
    {"id": "noisy_grand", "name": "Noisy-le-Grand", "lat": 48.849, "lng": 2.553},
    {"id": "chelles", "name": "Chelles", "lat": 48.878, "lng": 2.593},
    {"id": "torcy", "name": "Torcy", "lat": 48.851, "lng": 2.604},
    {"id": "lagny", "name": "Lagny-sur-Marne", "lat": 48.877, "lng": 2.607},
    {"id": "lognes", "name": "Lognes", "lat": 48.836, "lng": 2.629},
    {"id": "champs_marne", "name": "Champs-sur-Marne", "lat": 48.853, "lng": 2.602},
    {"id": "orly", "name": "Orly", "lat": 48.723, "lng": 2.359},
    {"id": "massy", "name": "Massy", "lat": 48.730, "lng": 2.271},
    {"id": "antony", "name": "Antony", "lat": 48.753, "lng": 2.297},
    {"id": "palaiseau", "name": "Palaiseau", "lat": 48.715, "lng": 2.243},
    {"id": "wissous", "name": "Wissous", "lat": 48.735, "lng": 2.327},
    {"id": "brunoy", "name": "Brunoy", "lat": 48.698, "lng": 2.504},
    {"id": "yerres", "name": "Yerres", "lat": 48.706, "lng": 2.489},
    {"id": "saint_maurice", "name": "Saint-Maurice", "lat": 48.818, "lng": 2.437},
    {"id": "thiais", "name": "Thiais", "lat": 48.764, "lng": 2.392},
    {"id": "cergy", "name": "Cergy", "lat": 49.036, "lng": 2.078},
]


def http_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": "carbon-clock-paris/air-refresh-1.0"})
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


def classify_region(lng, lat) -> str:
    d = haversine_km((lng, lat), PARIS_CORE)
    if d <= 4:
        return "paris"
    if d <= 13:
        return "banlieue"
    return "grande_couronne"


def in_region_bbox(site) -> bool:
    min_lon, min_lat, max_lon, max_lat = REGION_BBOX
    pad = 0.03
    return (
        min_lon - pad <= site["lng"] <= max_lon + pad
        and min_lat - pad <= site["lat"] <= max_lat + pad
    )


def normalize(xs):
    mx = max(xs) if xs else 1.0
    if mx <= 0:
        return [0.0] * len(xs)
    return [x / mx for x in xs]


def fetch_aq_point(site):
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
        payload = http_json(url, timeout=45)
    except Exception as exc:
        print(f"  fail {site['id']}: {exc}")
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
        "region": classify_region(site["lng"], site["lat"]),
    }


def main():
    import sys

    petite_only = "--petite-couronne" in sys.argv
    all_sites = []
    seen = set()
    sources = PARIS_AQ_SITES + REGION_AQ_SITES
    if not petite_only:
        sources = sources + GRANDE_COURONNE_AQ_SITES
    for site in sources:
        if site["id"] in seen or not in_region_bbox(site):
            continue
        seen.add(site["id"])
        all_sites.append(site)

    scope = "petite couronne" if petite_only else "petite & grande couronne"
    print(f"Fetching {len(all_sites)} air points (CAMS reels, Paris -> {scope})...")
    air = []
    for site in all_sites:
        st = fetch_aq_point(site)
        if st:
            air.append(st)
            print(f"  ok {site['id']} ({st.get('region', '?')})")

    (DATA / "airquality.json").write_text(json.dumps(air), encoding="utf-8")

    manifest_path = DATA / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["air_stations"] = len(air)
        manifest["built_at"] = datetime.now(timezone.utc).isoformat()
        note = f"Qualité de l'air : {len(air)} points CAMS nommés (Paris + {scope})."
        notes = list(manifest.get("notes") or [])
        notes = [n for n in notes if not n.startswith("Qualité de l'air :")]
        notes.append(note)
        manifest["notes"] = notes
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Done. {len(air)} stations written.")


if __name__ == "__main__":
    main()
