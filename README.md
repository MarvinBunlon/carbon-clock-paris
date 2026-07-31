# Carbon Clock — Paris

POC de data visualisation : **trafic × émissions × qualité de l’air** sur 24 h à Paris.

Inspiré de [The Carbon Clock — Manhattan](https://github.com/NirmitSachde/the-carbon-clock-manhattan), adapté aux données ouvertes françaises.

## Voir en local

```bash
python -m http.server 8090
```

Puis ouvrir http://127.0.0.1:8090/

## Ce que tu vois

| Couche | Source | Nature |
|--------|--------|--------|
| Axes / volumes | [Open Data Paris — comptages routiers](https://opendata.paris.fr/explore/dataset/comptages-routiers-permanents/) | Données réelles (journée complète) |
| Émissions CO₂ | Proxy volume × longueur × facteur flotte | Estimé |
| Qualité de l’air | [Open-Meteo / CAMS](https://open-meteo.com/en/docs/air-quality-api) (PM2.5, NO₂) | Données modèle |
| Flux animés | Géométrie réelle des arcs, horodatage synthétique | Synthétique |

## Problématique (profil Citizen Activist)

Le trafic parisien et le NO₂ partagent-ils le même rythme journalier ?  
Le POC croise deux familles de sources et mesure la corrélation (notamment aux heures de pointe).

## Rebuild des données

```bash
python preprocessing/build_data.py
```

## Stack

MapLibre GL + deck.gl · HTML/CSS/JS sans build · Python pour le preprocessing

## Mention

Fait avec l’aide de l’IA.
