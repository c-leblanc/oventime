# OvenTime

*L'électricité que vous consommez est-elle vraiment bas-carbone ? Ca dépend avant tout de **quand** est-ce que vous la consommez.*

**OvenTime** aide à décider **si c'est un bon moment pour utiliser un appareil gourmand en électricité**, en fonction de l'état du réseau électrique français.
Aperçu simple en temps réel du réseau électrique en France pour savoir s'il est plutôt **vert** (énergie bas-carbone abondamment disponible) ou s'il est plutôt **tendu** (toute consommation supplémentaire risque d'utiliser du gaz, et polluer).

Website : https://oventime.up.railway.app/

## Fonctionnalités

- **Diagnostic temps réel** du réseau électrique français (score de 0 à 150+)
- **Fenêtre de prix optimale** : identifie le meilleur créneau dans les prochaines heures (algorithme Otsu)
- **Notifications web push** en cas d'abondance d'énergie bas-carbone ou de forte tension sur le réseau

## Structure

```
src/oventime/
├── api/            # Endpoints FastAPI + frontend statique
├── cache/          # Cache SQLite des diagnostics
├── core/           # Logique métier (diagnostic, fenêtre de prix Otsu)
├── input/          # Acquisition de données (eco2mix, ENTSO-E) + stockage SQLite
├── interfaces/     # Formatage des messages
├── jobs/           # Orchestrateur de tâches de fond, notifications web push
├── config.py       # Configuration (tokens, seuils, paramètres)
├── main.py         # Point d'entrée (FastAPI + uvicorn)
└── utils.py        # Utilitaires (timestamps, parsing de dates)
```

## Tests

```bash
PYTHONPATH=src pytest
```

## Sources de données

- **RTE** — Données éCO2mix nationales temps réel : https://odre.opendatasoft.com/explore/dataset/eco2mix-national-tr
- **ENTSO-E** — Transparency Platform (prix day-ahead) : https://transparency.entsoe.eu/
