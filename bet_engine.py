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
    # Griglia 6x6 per i risultati esatti (0-5 gol)
    probs = np.array([[poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a) for j in range(6)] for i in range(6)])
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def update_stats_from_api():
    """Aggiorna le statistiche gestendo le differenze di nome tra le API."""
    url = "https://api.football-data.org/v4/competitions/SA/standings"
    headers = {"X-Auth-Token": os.environ.get("FOOTBALL_DATA_API_KEY")}
    response = requests.get(url, headers=headers)
    
    # Dizionario di traduzione: "Nome Football-Data": "Nome Odds-API"
    # Aggiungi qui le altre se noti discrepanze in Supabase
    mapping = {
        "FC Internazionale Milano": "Inter Milan",
        "AS Roma": "Roma",
        "SS Lazio": "Lazio",
        "AC Milan": "AC Milan",
        "SSC Napoli": "Napoli",
        "Juventus FC": "Juventus",
        "ACF Fiorentina": "Fiorentina",
        "Atalanta BC": "Atalanta",
        "Bologna FC 1909": "Bologna",
        "Torino FC": "Torino",
        "Hellas Verona FC": "Verona",
        "Udinese Calcio": "Udinese",
        "Empoli FC": "Empoli",
        "US Lecce": "Lecce",
        "AC Monza": "Monza",
        "Cagliari Calcio": "Cagliari",
        "Genoa CFC": "Genoa",
        "Parma Calcio 1913": "Parma",
        "Venezia FC": "Venezia",
        "Como 1907": "Como"
    }

    if response.status_code == 200:
        data = response.json()
        for team_info in data['standings'][0]['table']:
            raw_name = team_info['team']['name']
            name = mapping.get(raw_name, raw_name)
            
            played = team_info['playedGames']
            if played > 0:
                scored = team_info['goalsFor'] / played
                conceded = team_info['goalsAgainst'] / played
                
                # Upsert: inserisce se manca, aggiorna se esiste (basato su team_name)
                supabase.table("teams").upsert({
                    "team_name": name,
                    "avg_scored": round(scored, 2),
                    "avg_conceded": round(conceded, 2)
                }, on_conflict="team_name").execute()
        print("DEBUG: Statistiche sincronizzate.")

def fetch_and_populate_matches():
    """Scarica le prossime partite da The Odds API."""
    api_key = os.environ.get("ODDS_API_KEY")
    url = f"https://api.the-odds-api.com/v4/sports/soccer_italy_serie_a/odds/?apiKey={api_key}&regions=eu&markets=h2h"
    response = requests.get(url)
    
    if response.status_code == 200:
        matches = response.json()
        # Puliamo la tabella prima di inserire i nuovi match
        supabase.table("matches").delete().neq("id", 0).execute()
        
        for m in matches:
            supabase.table("matches").insert({
                "home_team_name": m['home_team'],
                "away_team_name": m['away_team'],
                "match_date": m['commence_time'],
                "status": "scheduled",
                "league": "Serie A"
            }).execute()
        print(f"DEBUG: {len(matches)} match inseriti.")
    else:
        print(f"DEBUG: Errore API Odds: {response.status_code}")

def run_analysis():
    print("DEBUG: Avvio procedura...")
    update_stats_from_api()
    fetch_and_populate_matches()
    
    # Recupero dati per l'analisi
    matches = supabase.table("matches").select("*").execute().data
    stats = supabase.table("teams").select("*").execute().data # Leggiamo direttamente da teams
    stats_map = {s['team_name']: s for s in stats}
    
    picks = []
    for m in matches:
        s_home = stats_map.get(m['home_team_name'])
        s_away = stats_map.get(m['away_team_name'])
        
        if s_home and s_away:
            # Calcolo Poisson
            p_home, _, _ = get_poisson_probs(s_home['avg_scored'], s_home['avg_conceded'], 
                                             s_away['avg_scored'], s_away['avg_conceded'], 1.5, 1.2)
            
            # Soglia di esempio: 0.50 (50%)
            if p_home > 0.50:
                picks.append(f"✅ {m['home_team_name']} vs {m['away_team_name']} (P: {round(p_home, 2)})")

    if picks:
        send_telegram_msg("🚀 *Analisi Giornaliera Serie A*\n\n" + "\n".join(picks))
    else:
        send_telegram_msg("⚠️ Analisi completata: nessun match di valore oggi.")

if __name__ == "__main__":
    run_analysis()
