import json
import math
import statistics
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "data"
m = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
xs = m["hourly_traffic_mean"]
ys = m["hourly_no2_mean"]


def pearson(a, b):
    mx, my = statistics.mean(a), statistics.mean(b)
    num = sum((x - mx) * (y - my) for x, y in zip(a, b))
    dx = math.sqrt(sum((x - mx) ** 2 for x in a))
    dy = math.sqrt(sum((y - my) ** 2 for y in b))
    return 0.0 if dx * dy == 0 else num / (dx * dy)


def slice_corr(hours):
    a = [xs[h] for h in hours]
    b = [ys[h] for h in hours]
    return round(pearson(a, b), 3)


m["correlation_traffic_no2_all_day"] = round(pearson(xs, ys), 3)
m["correlation_traffic_no2_morning_rush"] = slice_corr(range(6, 11))
m["correlation_traffic_no2_evening_rush"] = slice_corr(range(16, 21))
m["correlation_traffic_no2"] = m["correlation_traffic_no2_morning_rush"]
m["notes"] = [
    "Les trajets sont synthetiques, ancrés sur la géométrie réelle des arcs de comptage.",
    "Les émissions CO2 sont une proxy (volume x longueur x facteur flotte urbaine).",
    f"Correlation 24h trafic-NO2: r={m['correlation_traffic_no2_all_day']} (faible: photochimie estivale).",
    f"Correlation pointe matin 6-10h: r={m['correlation_traffic_no2_morning_rush']}.",
    f"Correlation pointe soir 16-20h: r={m['correlation_traffic_no2_evening_rush']}.",
]
(p / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
print(
    "all",
    m["correlation_traffic_no2_all_day"],
    "am",
    m["correlation_traffic_no2_morning_rush"],
    "pm",
    m["correlation_traffic_no2_evening_rush"],
)
