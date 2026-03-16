import os
import numpy as np
import requests
import time
from scipy.stats import poisson
from supabase import create_client

# Setup Connessioni
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# Mappatura Leghe: Football-Data Code -> The Odds API Key
LEAGUES = {
    'SA': 'soccer_italy_serie_a',
    'PL': 'soccer_epl',
    'PD': 'soccer_spain_la_liga',
    'BL1': 'soccer_germany_bundesliga',
    'FL1': 'soccer_france_ligue_one'  # Nome corretto per The Odds API
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
    """Aggiorna statistiche e gestisce il mapping dei nomi tra le due API."""
    headers = {"X-Auth-Token": os.environ.get("FOOTBALL_DATA_API_KEY")}
    
    # Dizionario di traduzione: "Nome Football-Data": "Nome Odds-API"
    mapping = {
        # ITALIA
        "FC Internazionale Milano": "Inter Milan", "Juventus FC": "Juventus",
        "AS Roma": "Roma", "SS Lazio": "Lazio", "AC Milan": "AC Milan",
        "SSC Napoli": "Napoli", "ACF Fiorentina": "Fiorentina", "Atalanta BC": "Atalanta",
        "Bologna FC 1909": "Bologna", "Torino FC": "Torino", "Hellas Verona FC": "Verona",
        # INGHILTERRA
        "Manchester City FC": "Manchester City", "Manchester United FC": "Manchester United",
        "Arsenal FC": "Arsenal", "Tottenham Hotspur FC": "Tottenham Hotspur",
        "Liverpool FC": "Liverpool", "Chelsea FC": "Chelsea", "Aston Villa FC": "Aston Villa",
        # SPAGNA
        "Real Madrid CF": "Real Madrid", "FC Barcelona": "Barcelona",
        "Club Atlético de Madrid": "Atletico Madrid", "Sevilla FC": "Sevilla",
        "Real Sociedad de Fútbol": "Real Sociedad", "Villarreal CF": "Villarreal",
        # GERMANIA
        "FC Bayern München": "Bayern Munich", "Borussia Dortmund": "Borussia Dortmund",
        "Bayer 04 Leverkusen": "Bayer Leverkusen", "RB Leipzig": "RB Leipzig",
        # FRANCIA
        "Paris Saint-Germain FC": "Paris Saint Germain", "Olympique de Marseille": "Marseille",
        "AS Monaco FC": "Monaco", "Olympique Lyonnais": "Lyon", "Lille OSC": "Lille"
    }

    for code in LEAGUES.keys():
        print(f"--- DEBUG: Recupero classifica per {code} ---")
        url = f"https://api.football-data.org/v4/competitions/{code}/standings"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if 'standings' in data and len(data['standings']) > 0:
                    for team_info in data['standings'][0]['table']:
                        raw_name = team_info['team']['name']
                        name = mapping.get(raw_name, raw_name)
                        played = team_info['playedGames']
                        if played > 0:
                            scored = team_info['goalsFor'] / played
                            conceded = team_info['goalsAgainst'] / played
                            supabase.table("teams").upsert({
                                "team_name": name, "avg_scored": round(scored, 2), "avg_conceded": round(conceded, 2)
                            }, on_conflict="team_name").execute()
                    print(f"SUCCESS: Statistiche {code} caricate.")
            else:
                print(f"ERROR: {code} ha restituito {response.status_code}")
        except Exception as e:
            print(f"EXCEPTION {code}: {e}")
        time.sleep(6) # Rispetto del rate limit di 10 chiamate/min

def fetch_and_populate_matches():
    """Svuota e ripopola i match futuri."""
    api_key = os.environ.get("ODDS_API_KEY")
    supabase.table("matches").delete().neq("id", 0).execute()
    
    for code, api_name in LEAGUES.items():
        url = f"https://api.the-odds-api.com/v4/sports/{api_name}/odds/?apiKey={api_key}&regions=eu&markets=h2h"
        try:
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
        except Exception as e:
            print(f"EXCEPTION MATCHES {code}: {e}")
        time.sleep(1)

def run_analysis():
    print("DEBUG: Avvio Analisi Big 5...")
    update_stats_from_api()
    fetch_and_populate_matches()
    
    matches = supabase.table("matches").select("*").execute().data
    stats = supabase.table("teams").select("*").execute().data
    stats_map = {s['team_name']: s for s in stats}
    
    print(f"DEBUG: Totale squadre mappate nel DB: {len(stats_map)}")
    
    picks = []
    for m in matches:
        s_home = stats_map.get(m['home_team_name'])
        s_away = stats_map.get(m['away_team_name'])
        
        # Analisi solo se abbiamo le statistiche di entrambe le squadre
        if s_home and s_away:
            p_home, _, _ = get_poisson_probs(s_home['avg_scored'], s_home['avg_conceded'], 
                                             s_away['avg_scored'], s_away['avg_conceded'], 1.5, 1.2)
            
            # Soglia test 0.30 per verificare l'invio
            if p_home > 0.30:
                picks.append(f"⚽ [{m['league']}] *{m['home_team_name']}* vs {m['away_team_name']} \n   Prob. Vittoria Casa: *{round(p_home * 100, 1)}%*")

    if picks:
        # Invio a Telegram (limite di 10 pick per non fare spam)
        header = "🌍 *ANALISI BIG 5 EUROPEI* 🌍\n\n"
        send_telegram_msg(header + "\n\n".join(picks[:10]))
    else:
        send_telegram_msg("⚠️ Analisi completata: nessun match soddisfa i criteri attuali.")

if __name__ == "__main__":
    run_analysis()
