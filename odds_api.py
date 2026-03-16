import os
import requests

API_KEY = os.environ.get("ODDS_API_KEY")

def get_matches():

    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    params = {
        "apiKey": API_KEY,
        "regions": "eu",
        "markets": "h2h"
    }

    response = requests.get(url, params=params)
    data = response.json()

    print("API RESPONSE:", data)

    matches = []

    if not isinstance(data, list):
        print("Errore API:", data)
        return matches

    for game in data:

        home = game["home_team"]
        away = game["away_team"]

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        market = bookmakers[0]["markets"][0]["outcomes"]

        odds_map = {}
        for o in market:
            odds_map[o["name"]] = o["price"]

        if home not in odds_map or away not in odds_map or "Draw" not in odds_map:
            continue

        matches.append({
            "match": f"{home} vs {away}",
            "odds": [
                odds_map[home],
                odds_map["Draw"],
                odds_map[away]
            ]
        })

    print("MATCHES FOUND:", len(matches))

    return matches
