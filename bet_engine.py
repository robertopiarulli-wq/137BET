import os
import numpy as np
import requests
from scipy.stats import poisson
from supabase import create_client

# Setup Connessioni
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
ALPHA = 0.0073 

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
    """Aggiorna le statistiche in Supabase con dati reali di football-data.org"""
    url = "https://api.football-data.org/v4/competitions/SA/standings"
    headers = {"X-Auth-Token": os.environ.get("FOOTBALL_DATA_API_KEY")}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        for team_info in data['standings'][0]['table']:
            name = team_info['team']['name']
            played = team_info['playedGames']
            # Evita divisione per zero se la stagione è appena iniziata
            if played > 0:
                scored = team_info['goalsFor'] / played
                conceded = team_info['goalsAgainst'] / played
                
                # Aggiorna il database
                supabase.table("teams").update({
                    "avg_scored": round(scored, 2),
                    "avg_conceded": round(conceded, 2)
                }).eq("team_name", name).execute()
        print("DEBUG: Statistiche aggiornate con successo.")

def fetch_and_populate_matches():
    """Scarica le prossime partite da The Odds API."""
    api_key = os.environ.get("ODDS_API_KEY")
    url = f"https://api.the-odds-api.com/v4/sports/soccer_italy_serie_a/odds/?apiKey={api_key}&regions=eu&markets=h2h"
    response = requests.get(url)
    
    if response.status_code == 200:
        matches = response.json()
        supabase.table("matches").delete().neq("id", 0).execute()
        for m in matches:
            supabase.table("matches").insert({
                "home_team_name": m['home_team'],
                "away_team_name": m['away_team'],
                "match_date": m['commence_time'],
                "status": "scheduled",
                "league": "Serie A"
            }).execute()
        print("DEBUG: Matches aggiornati.")

def run_analysis():
    print("DEBUG: Avvio procedura...")
    
    # 1. Aggiorna le statistiche reali
    update_stats_from_api()
    
    # 2. Aggiorna i match
    fetch_and_populate_matches()
    
    # 3. Analisi
    matches = supabase.table("matches").select("*").execute().data
    stats = supabase.table("view_team_stats").select("*").execute().data
    stats_map = {s['team_name']: s for s in stats}
    
    picks = []
    for m in matches:
        s_home = stats_map.get(m['home_team_name'])
        s_away = stats_map.get(m['away_team_name'])
        
        if s_home and s_away:
            p_home, _, _ = get_poisson_probs(s_home['avg_scored'], s_home['avg_conceded'], 
                                             s_away['avg_scored'], s_away['avg_conceded'], 1.5, 1.2)
            if p_home > 0.50:
                picks.append(f"{m['home_team_name']} vs {m['away_team_name']}")

    if picks:
        send_telegram_msg("🚀 *Analisi:* \n" + "\n".join(picks[:3]))
    else:
        send_telegram_msg("⚠️ Nessun match soddisfa i parametri.")

if __name__ == "__main__":
    run_analysis()
