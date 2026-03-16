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
    lam_h = att_h * def_a * avg_h
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

def fetch_and_populate_matches():
    """Scarica quote e popola la tabella matches con i nomi delle squadre."""
    api_key = os.environ.get("ODDS_API_KEY")
    url = f"https://api.the-odds-api.com/v4/sports/soccer_italy_serie_a/odds/?apiKey={api_key}&regions=eu&markets=h2h"
    response = requests.get(url)
    
    if response.status_code == 200:
        matches = response.json()
        print(f"DEBUG: Recuperati {len(matches)} match da API.")
        for m in matches:
            # Inseriamo i dati basandoci sulle nuove colonne 'home_team_name' e 'away_team_name'
            supabase.table("matches").insert({
                "home_team_name": m['home_team'],
                "away_team_name": m['away_team'],
                "status": "scheduled",
                "league": "Serie A"
            }).execute()
        print("DEBUG: Database popolato con successo.")
    else:
        print(f"DEBUG: Errore API Odds: {response.status_code}")

def run_analysis():
    print("DEBUG: Avvio procedura...")
    
    # 1. Pulizia tabella prima di nuovi inserimenti (opzionale, evita duplicati)
    supabase.table("matches").delete().neq("id", 0).execute()
    
    # 2. Popolamento automatico
    fetch_and_populate_matches()
    
    # 3. Recupero Dati
    matches = supabase.table("matches").select("*").eq("status", "scheduled").execute().data
    
    # Nota: Assicurati che 'view_team_stats' sia ricostruita coerentemente con i nomi squadra
    stats = supabase.table("view_team_stats").select("*").execute().data
    stats_map = {s['team_name']: s for s in stats} # Mappiamo per nome, non più ID
    
    picks = []
    for m in matches:
        s_home = stats_map.get(m['home_team_name'])
        s_away = stats_map.get(m['away_team_name'])
        
        if s_home and s_away:
            p_home, _, _ = get_poisson_probs(s_home['avg_scored'], s_home['avg_conceded'], 
                                             s_away['avg_scored'], s_away['avg_conceded'], 1.5, 1.2)
            
            edge = p_home - 0.50 
            if edge > ALPHA:
                picks.append({'match': f"{m['home_team_name']} vs {m['away_team_name']}", 'p_win': p_home})

    # 4. Output
    if picks:
        msg = "🚀 *Bet Engine: Analisi Completata*\n" + "\n".join([p['match'] for p in picks[:3]])
        send_telegram_msg(msg)
    else:
        print("DEBUG: Nessuna combinazione valida.")
        send_telegram_msg("⚠️ Analisi completata: nessuna combinazione soddisfa il filtro Alfa.")

if __name__ == "__main__":
    run_analysis()
