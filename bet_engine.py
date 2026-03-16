import os
import numpy as np
import requests
import time
from datetime import datetime, timedelta, timezone
from scipy.stats import poisson
from supabase import create_client
from thefuzz import process

# Setup
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
LEAGUES = {'SA': 'soccer_italy_serie_a', 'PL': 'soccer_epl', 'PD': 'soccer_spain_la_liga', 'BL1': 'soccer_germany_bundesliga', 'FL1': 'soccer_france_ligue_one'}

def get_full_analysis(att_h, def_h, att_a, def_a, avg_h, avg_a):
    lam_h = att_h * def_a * avg_h
    lam_a = att_a * def_h * avg_a
    probs = np.array([[poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a) for j in range(6)] for i in range(6)])
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

def fetch_and_populate_matches():
    api_key = os.environ.get("ODDS_API_KEY")
    supabase.table("matches").delete().neq("id", 0).execute()
    for code, api_name in LEAGUES.items():
        url = f"https://api.the-odds-api.com/v4/sports/{api_name}/odds/?apiKey={api_key}&regions=eu&markets=h2h"
        try:
            response = requests.get(url, timeout=15).json()
            for m in response:
                odds = m['bookmakers'][0]['markets'][0]['outcomes']
                o1 = next((o['price'] for o in odds if o['name'] == m['home_team']), 1.0)
                ox = next((o['price'] for o in odds if o['name'] == 'Draw'), 1.0)
                o2 = next((o['price'] for o in odds if o['name'] == m['away_team']), 1.0)
                supabase.table("matches").insert({
                    "home_team_name": m['home_team'], "away_team_name": m['away_team'],
                    "match_date": m['commence_time'], "league": code,
                    "odds_1": o1, "odds_x": ox, "odds_2": o2
                }).execute()
        except: continue

def run_analysis():
    update_stats_from_api() # (funzione esistente)
    fetch_and_populate_matches()
    
    matches = supabase.table("matches").select("*").execute().data
    stats_map = {s['team_name']: s for s in supabase.table("teams").select("*").execute().data}
    
    candidates = []
    for m in matches:
        s_h = stats_map.get(find_best_match(m['home_team_name'], list(stats_map.keys())))
        s_a = stats_map.get(find_best_match(m['away_team_name'], list(stats_map.keys())))
        
        if s_h and s_a:
            p1, px, p2 = get_full_analysis(s_h['avg_scored'], s_h['avg_conceded'], s_a['avg_scored'], s_a['avg_conceded'], 1.5, 1.2)
            
            # Calcolo Valore (EV)
            for segno, prob, quota in [('1', p1, m['odds_1']), ('X', px, m['odds_x']), ('2', p2, m['odds_2'])]:
                ev = (prob * quota) - 1
                if ev > 0.08: # Scegliamo solo giocate con valore > 8%
                    candidates.append({"match": f"{m['home_team_name']} vs {m['away_team_name']}", "segno": segno, "ev": ev, "quota": quota})

    # Generazione Schedina: prendiamo i 3 eventi con valore (EV) più alto
    best_bets = sorted(candidates, key=lambda x: x['ev'], reverse=True)[:3]
    
    if best_bets:
        total_odds = 1.0
        for b in best_bets: total_odds *= b['quota']
        msg = "🚀 *SCHEDINA OTTIMIZZATA (VALORE > 8%)*\n\n"
        for b in best_bets: msg += f"🏟 {b['match']} -> *{b['segno']}* @{b['quota']} (EV: {round(b['ev']*100,1)}%)\n"
        msg += f"\n💰 Quota Totale stimata: *{round(total_odds, 2)}*"
        send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
