# odds_api.py
import os
import requests

API_KEY = os.environ.get("ODDS_API_KEY")

# principali 5 campionati
LEAGUES = [
    "soccer_epl",
    "soccer_italy_serie_a",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one"
]

def get_all_matches():
    matches = []
    for league in LEAGUES:
        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
        params = {"apiKey": API_KEY, "regions": "eu", "markets": "h2h"}
        resp = requests.get(url, params=params).json()

        if not isinstance(resp, list):
            print(f"Errore API {league}: {resp}")
            continue

        for g in resp:
            home = g['home_team']
            away = g['away_team']

            bookmakers = g.get('bookmakers', [])
            if not bookmakers:
                continue

            market = bookmakers[0]['markets'][0]['outcomes']
            odds_map = {o['name']: o['price'] for o in market}

            if home not in odds_map or away not in odds_map or "Draw" not in odds_map:
                continue

            matches.append({
                "league": league,
                "match": f"{home} vs {away}",
                "odds": [odds_map[home], odds_map["Draw"], odds_map[away]]
            })
    return matches
