# Carbon Clock

Visualisation interactive croisant **trafic routier**, **émissions CO₂** et **qualité de l’air** sur un cycle de 24 heures, pour Paris, Lyon et Marseille.

Projet créatif de fin d’études — OFA EPITA, Majeure DEV.  
Inspiré de [The Carbon Clock — Manhattan](https://github.com/NirmitSachde/the-carbon-clock-manhattan), adapté aux données ouvertes françaises.

## Objectif

Mesurer et visualiser la corrélation entre le profil horaire du trafic et le NO₂, en particulier aux heures de pointe. Le prototype s’adresse à un profil *Citizen Activist* : lire le « pouls » urbain sans expertise technique préalable.

## Fonctionnalités

- Carte immersive multi-villes (Paris, Lyon, Marseille)
- Couches superposées : axes, flux animés, émissions, stations air
- Scrubber temporel sur 24 h
- Vue d’analyse croisée (corrélations Pearson, profils horaires)

## Sources de données

| Couche | Source | Nature |
|--------|--------|--------|
| Axes / volumes | [Open Data Paris — comptages routiers](https://opendata.paris.fr/explore/dataset/comptages-routiers-permanents/) | Données réelles |
| Axes régionaux | OpenStreetMap (Overpass) | Géométrie réelle, intensités calées |
| Émissions CO₂ | Proxy volume × longueur × facteur flotte | Estimé |
| Qualité de l’air | [Open-Meteo / CAMS](https://open-meteo.com/en/docs/air-quality-api) (PM2.5, NO₂) | Modèle |
| Flux animés | Géométrie des arcs, horodatage synthétique | Synthétique |

## Installation et exécution

Prérequis : Python 3.

```bash
python -m http.server 8090
```

Ouvrir [http://127.0.0.1:8090/](http://127.0.0.1:8090/).

## Reconstruction des données

```bash
python preprocessing/build_data.py
```

Scripts complémentaires dans `preprocessing/` (air, émissions, multi-villes).

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Front-end | HTML / CSS / JavaScript (sans bundler) |
| Cartographie | MapLibre GL, deck.gl |
| Preprocessing | Python |

## Auteurs

- Marvin Bunlon
- Raphaël Lelièvre

## Licence des données

Les jeux de données utilisés restent la propriété de leurs éditeurs respectifs (Ville de Paris, OpenStreetMap, Copernicus / Open-Meteo). Consulter les conditions d’usage de chaque source.
