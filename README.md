# OvenTime

*L'électricité que vous consommez est-elle vraiment bas-carbone ? Ca dépend avant tout de **quand** est-ce que vous la consommez.*

**OvenTime** est un bot Telegram qui aide à décider **si c’est un bon moment pour utiliser un appareil gourmand en électricité**, en fonction de l’état du réseau électrique français. ⚡🍳
Il donne un aperçu simple en temps réel du réseau électrique en France pour savoir s’il est plutôt 🍃 **vert** 🍃 (énergie bas-carbone abondamment disponible) ou s’il est plutôt 🔥 **tendu** 🔥, ce qui implique que toute consommation supplémentaire risque d’utiliser du gaz (et polluer).

👉 Interrogez-le pour savoir si c'est un moment eco-friendly pour démarrer quelque chose qui consomme beaucoup d'électricité (la pyrolise du four, le lave-linge, le sèche-linge...)

Bot Telegram : https://t.me/oventime_bot

## Commandes

| Commande | Description |
|----------|------------|
| `/m` | État du système électrique à l'instant (dernières données disponibles) |
| `/a <heure>` | État du système électrique à un moment précis de la semaine passée (ex : `/a 15:30`, `/a hier 9am`) |
| `/start_auto` | Active un message d'alerte en cas d'électricité bas-carbone abondante |
| `/stop_auto` | Désactive le message d'alerte en cas d'électricité bas-carbone abondante |

## Structure

- src/oven_time : logique principale (bot, API, traitement des données)
- requirements.txt : dépendances Python
- run_bot.py : script d’entrée