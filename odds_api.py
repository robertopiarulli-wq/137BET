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

    # stampa debug per GitHub logs
    print("API RESPONSE:", data)

    # se non è lista → errore API
    if not isinstance(data, list):
        print("Errore API:", data)
        return []

    matches = []

    for game in data:

        teams = game["teams"]
        home = game["home_team"]

        bookmaker = game["bookmakers"][0]
        odds = bookmaker["markets"][0]["outcomes"]

        odds_map = {}

        for o in odds:
            odds_map[o["name"]] = o["price"]

        if len(odds_map) < 3:
            continue

        matches.append({
            "match": f"{teams[0]} vs {teams[1]}",
            "odds": [
                odds_map.get(home),
                odds_map.get("Draw"),
                odds_map.get(teams[1] if teams[0]==home else teams[0])
            ]
        })

    print("MATCHES FOUND:", len(matches))

    return matches
