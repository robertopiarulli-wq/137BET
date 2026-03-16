import os
import numpy as np
import requests
import time
from datetime import datetime, timedelta, timezone
from scipy.stats import poisson
from supabase import create_client
from thefuzz import process

# Setup Connessioni
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

LEAGUES = {
    'SA': 'soccer_italy_serie_a',
    'PL': 'soccer_epl',
    'PD': 'soccer_spain_la_liga',
    'BL1': 'soccer_germany_bundesliga',
    'FL1': 'soccer_france_ligue_one'
}

def format_date(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime("%d/%m %H:%M")
    except: return "Data N.D."

def find_best_match(name, choices, threshold=80):
    best_match, score = process.extractOne(name, choices)
    return best_match if score >= threshold else None

def get_poisson_probs(att_h, def_h, att_a, def_a, avg_h, avg_a):
    lam_h = att_h * def_a * avg_h
    lam_a = att_a * def_h * avg_a
    probs = np.array([[poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a) for j in range(6)] for i in range(6)])
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

def update_stats_from_api():
    print("DEBUG: Avvio aggiornamento statistiche...")
    headers = {"X-Auth-Token": os.environ.get("FOOTBALL_DATA_API_KEY")}
    for code in LEAGUES.keys():
        url = f"https://api.football-data.org/v4/competitions/{code}/standings"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for team_info in data['standings'][0]['table']:
                    played = team_info['playedGames']
                    if played > 0:
                        supabase.table("teams").upsert({
                            "team_name": team_info['team']['name'],
                            "avg_scored": round(team_info['goalsFor'] / played, 2),
                            "avg_conceded": round(team_info['goalsAgainst'] / played, 2)
                        }, on_conflict="team_name").execute()
                print(f"SUCCESS: {code} aggiornato.")
        except Exception as e:
            print(f"ERROR {code}: {e}")
        time.sleep(6)

def fetch_and_populate_matches():
    print("DEBUG: Avvio recupero partite...")
    api_key = os.environ.get("ODDS_API_KEY")
    supabase.table("matches").delete().neq("id", 0).execute()
    
    limit_date = datetime.now(timezone.utc) + timedelta(days=7)
    
    for code, api_name in LEAGUES.items():
        print(f"DEBUG: Recupero quote per {code}...")
        url = f"https://api.the-odds-api.com/v4/sports/{api_name}/odds/?apiKey={api_key}&regions=eu&markets=h2h"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                matches = response.json()
                count = 0
                for m in matches:
                    match_dt = datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                    if match_dt < limit_date:
                        supabase.table("matches").insert({
                            "home_team_name": m['home_team'], "away_team_name": m['away_team'],
                            "match_date": m['commence_time'], "status": "scheduled", "league": code
                        }).execute()
                        count += 1
                print(f"DEBUG: {count} match inseriti per {code}.")
            else:
                print(f"ERROR: API Quote {code} ha restituito status {response.status_code}. Msg: {response.text}")
        except Exception as e:
            print(f"EXCEPTION CRITICA su {code}: {e}")
        time.sleep(2)

def run_analysis():
    update_stats_from_api()
    fetch_and_populate_matches()
    
    matches = supabase.table("matches").select("*").execute().data
    stats = supabase.table("teams").select("*").execute().data
    stats_map = {s['team_name']: s for s in stats}
    db_team_names = list(stats_map.keys())
    
    picks = []
    for m in matches:
        home_name = find_best_match(m['home_team_name'], db_team_names)
        away_name = find_best_match(m['away_team_name'], db_team_names)
        
        s_home = stats_map.get(home_name)
        s_away = stats_map.get(away_name)
        
        if s_home and s_away:
            p_home, _, _ = get_poisson_probs(s_home['avg_scored'], s_home['avg_conceded'], 
                                             s_away['avg_scored'], s_away['avg_conceded'], 1.5, 1.2)
            if p_home > 0.50:
                picks.append(f"📅 *{format_date(m['match_date'])}* - [{m['league']}]\n🏟 *{m['home_team_name']}* vs {m['away_team_name']}\n📈 Vittoria Casa: *{round(p_home * 100, 1)}%*")

    if picks:
        send_telegram_msg("🌍 *ANALISI BIG 5 EUROPEI* 🌍\n\n" + "\n\n".join(picks[:10]))
    else:
        send_telegram_msg("⚠️ Analisi completata: nessun match a breve termine soddisfa i criteri.")

if __name__ == "__main__":
    run_analysis()
