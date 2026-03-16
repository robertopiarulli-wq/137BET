import os
import numpy as np
import requests
from scipy.stats import poisson
from supabase import create_client

# Setup Connessioni
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
ALPHA = 0.0073 

# Mappatura Codici Campionato (Football-Data: Odds-API)
LEAGUES = {
    'SA': 'soccer_italy_serie_a',
    'PL': 'soccer_epl',
    'PD': 'soccer_spain_la_liga',
    'BL1': 'soccer_germany_bundesliga',
    'FL1': 'soccer_france_ligue_1'
}

def get_poisson_probs(att_h, def_h, att_a, def_a, avg_h, avg_a):
    lam_h = att_h * def_a * avg_h
    lam_a = att_a * def_h * avg_a
    probs = np.array([[poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a) for j in range(6)] for i in range(6)])
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def update_stats_from_api():
    """Aggiorna le statistiche per tutti i Big 5."""
    headers = {"X-Auth-Token": os.environ.get("FOOTBALL_DATA_API_KEY")}
    
    # Mapping esteso per i Big 5 (Aggiungi qui man mano che trovi differenze)
    mapping = {
        "FC Internazionale Milano": "Inter Milan",
        "Juventus FC": "Juventus",
        "FC Bayern München": "Bayern Munich",
        "Real Madrid CF": "Real Madrid",
        "Paris Saint-Germain FC": "Paris Saint Germain",
        "Manchester City FC": "Manchester City",
        "Arsenal FC": "Arsenal",
        "Bayer 04 Leverkusen": "Bayer Leverkusen"
    }

    for code in LEAGUES.keys():
        url = f"https://api.football-data.org/v4/competitions/{code}/standings"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            for team_info in data['standings'][0]['table']:
                raw_name = team_info['team']['name']
                name = mapping.get(raw_name, raw_name)
                played = team_info['playedGames']
                if played > 0:
                    scored = team_info['goalsFor'] / played
                    conceded = team_info['goalsAgainst'] / played
                    supabase.table("teams").upsert({
                        "team_name": name,
                        "avg_scored": round(scored, 2),
                        "avg_conceded": round(conceded, 2)
                    }, on_conflict="team_name").execute()
            print(f"DEBUG: Statistiche {code} aggiornate.")

def fetch_and_populate_matches():
    """Scarica le prossime partite per tutti i Big 5."""
    api_key = os.environ.get("ODDS_API_KEY")
    supabase.table("matches").delete().neq("id", 0).execute() # Reset totale
    
    for code, api_name in LEAGUES.items():
        url = f"https://api.the-odds-api.com/v4/sports/{api_name}/odds/?apiKey={api_key}&regions=eu&markets=h2h"
        response = requests.get(url)
        
        if response.status_code == 200:
            matches = response.json()
            for m in matches:
                supabase.table("matches").insert({
                    "home_team_name": m['home_team'],
                    "away_team_name": m['away_team'],
                    "match_date": m['commence_time'],
                    "status": "scheduled",
                    "league": code
                }).execute()
            print(f"DEBUG: Match {code} inseriti.")

def run_analysis():
    print("DEBUG: Avvio Analisi Big 5...")
    update_stats_from_api()
    fetch_and_populate_matches()
    
    matches = supabase.table("matches").select("*").execute().data
    stats = supabase.table("teams").select("*").execute().data
    stats_map = {s['team_name']: s for s in stats}
    
    picks = []
    for m in matches:
        s_home = stats_map.get(m['home_team_name'])
        s_away = stats_map.get(m['away_team_name'])
        
        if s_home and s_away:
            p_home, _, _ = get_poisson_probs(s_home['avg_scored'], s_home['avg_conceded'], 
                                             s_away['avg_scored'], s_away['avg_conceded'], 1.5, 1.2)
            if p_home > 0.55: # Alzata leggermente la soglia per i Big 5
                picks.append(f"[{m['league']}] {m['home_team_name']} vs {m['away_team_name']} (P: {round(p_home, 2)})")

    if picks:
        send_telegram_msg("🌍 *Analisi Big 5 Europei*\n\n" + "\n".join(picks))
    else:
        send_telegram_msg("⚠️ Nessun match di valore nei Big 5 oggi.")

if __name__ == "__main__":
    run_analysis()
