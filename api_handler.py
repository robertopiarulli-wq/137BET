import os
import requests
from config import COMPETITION_CODE

FOOTBALL_DATA_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY")

def get_daily_odds():
    """
    Scarica i match del giorno da Football‑Data.org.
    If quotes are provided in the API response (average post‑match odds),
    include them per match.
    """
    url = "https://api.football-data.org/v4/matches"
    headers = {
        'X-Auth-Token': FOOTBALL_DATA_API_KEY
    }
    response = requests.get(url, headers=headers).json()
    partite = []

    for m in response.get("matches", []):
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]

        # Football‑Data may include odds fields if available under 'odds'
        odds_data = m.get("odds")
        if odds_data:
            quote_1 = odds_data.get("homeWin", None)
            quote_X = odds_data.get("draw", None)
            quote_2 = odds_data.get("awayWin", None)

            if quote_1 and quote_X and quote_2:
                partite.append({
                    "match": f"{home} - {away}",
                    "odds": [quote_1, quote_X, quote_2],
                    "market_move": 0.1,
                    "draw_factor": 0.05,
                    "strength": 0.2
                })

    return partite
