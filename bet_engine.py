import os
import numpy as np
import requests
from scipy.stats import poisson
from supabase import create_client
from itertools import combinations

# Setup Connessioni
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
ALPHA = 0.0073 

def get_poisson_probs(att_h, def_h, att_a, def_a, avg_h, avg_a):
    lam_h = att_h * def_h * avg_h
    lam_a = att_a * def_h * avg_a
    probs = np.array([[poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a) for j in range(6)] for i in range(6)])
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, data=payload)
    print(f"DEBUG: Risposta Telegram Status Code: {response.status_code}")

def update_team_stats(team_name):
    """Verifica se la squadra esiste, altrimenti la crea."""
    exists = supabase.table("teams").select("team_name").eq("team_name", team_name).execute().data
    if not exists:
        supabase.table("teams").insert({
            "team_name": team_name,
            "avg_scored": 1.2,
            "avg_conceded": 1.2
        }).execute()

def fetch_and_populate_matches():
    """Scarica quote e popola le tabelle."""
    api_key = os.environ.get("ODDS_API_KEY")
    url = f"https://api.the-odds-api.com/v4/sports/soccer_italy_serie_a/odds/?apiKey={api_key}&regions=eu&markets=h2h"
    response = requests.get(url)
    
    if response.status_code == 200:
        matches = response.json()
        print(f"DEBUG: Recuperati {len(matches)} match.")
        
        # Pulizia preventiva per evitare duplicati
        supabase.table("matches").delete().neq("id", 0).execute()
        
        for m in matches:
            # 1. Assicura che le squadre esistano in 'teams'
            update_team_stats(m['home_team'])
            update_team_stats(m['away_team'])
            
            # 2. Salva il match
            supabase.table("matches").insert({
                "home_team_name": m['home_team'],
                "away_team_name": m['away_team'],
                "match_date": m['commence_time'],
                "status": "scheduled",
                "league": "Serie A"
            }).execute()
        print("DEBUG: Database aggiornato.")
    else:
        print(f"DEBUG: Errore API Odds: {response.status_code}")

def run_analysis():
    print("DEBUG: Avvio procedura...")
    fetch_and_populate_matches()
    
    matches = supabase.table("matches").select("*").eq("status", "scheduled").execute().data
    stats = supabase.table("view_team_stats").select("*").execute().data
    stats_map = {s['team_name']: s for s in stats}
    
    picks = []
    for m in matches:
        s_home = stats_map.get(m['home_team_name'])
        s_away = stats_map.get(m['away_team_name'])
        
        if s_home and s_away:
            p_home, _, _ = get_poisson_probs(s_home['avg_scored'], s_home['avg_conceded'], 
                                             s_away['avg_scored'], s_away['avg_conceded'], 1.5, 1.2)
            
            # Qui potresti aggiungere la logica per confrontare con le quote reali
            if p_home > 0.50: # Esempio: probabilità superiore al 50%
                picks.append({'match': f"{m['home_team_name']} vs {m['away_team_name']}"})

    if picks:
        msg = "🚀 *Analisi:* \n" + "\n".join([p['match'] for p in picks[:3]])
        send_telegram_msg(msg)
    else:
        send_telegram_msg("⚠️ Nessun match soddisfa i parametri.")

if __name__ == "__main__":
    run_analysis()
