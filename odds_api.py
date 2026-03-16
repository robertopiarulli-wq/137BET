# odds_api.py
import requests
import os

API_KEY = os.environ.get("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/"

def get_all_matches():
    params = {
        "apiKey": API_KEY,
        "regions": "eu",
        "markets": "h2h"
    }
    response = requests.get(BASE_URL, params=params)
    if response.status_code != 200:
        print("Errore API:", response.json())
        return []
    return response.json()

def extract_match_info(match):
    """Estrae nomi squadre e quote EV dal primo bookmaker"""
    try:
        bookmakers = match.get('bookmakers', [])
        if not bookmakers:
            return "Team1", "Team2", [1,1,1]
        markets = bookmakers[0].get('markets', [])
        h2h_market = next((m for m in markets if m['key'] == 'h2h'), None)
        if not h2h_market:
            return "Team1", "Team2", [1,1,1]
        outcomes = h2h_market.get('outcomes', [])
        # ordina: [home, draw, away]
        home_name = outcomes[0]['name'] if outcomes[0]['name'].lower() != 'draw' else outcomes[1]['name']
        away_name = outcomes[1]['name'] if outcomes[1]['name'].lower() != 'draw' else outcomes[2]['name']
        home_price = next(o['price'] for o in outcomes if o['name'] == home_name)
        away_price = next(o['price'] for o in outcomes if o['name'] == away_name)
        draw_price = next((o['price'] for o in outcomes if o['name'].lower() == 'draw'), 1)
        return home_name, away_name, [home_price, draw_price, away_price]
    except:
        return "Team1", "Team2", [1,1,1]
