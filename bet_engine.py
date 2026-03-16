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

def format_date(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime("%d/%m %H:%M")
    except: return "Data N.D."

def find_best_match(name, choices, threshold=80):
    best_match, score = process.extractOne(name, choices)
    return best_match if score >= threshold else None

def get_full_analysis(att_h, def_h, att_a, def_a, avg_h, avg_a):
    lam_h = att_h * def_a * avg_h
    lam_a = att_a * def_h * avg_a
    probs = np.array([[poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a) for j in range(6)] for i in range(6)])
    p1 = np.sum(np.tril(probs, -1))
    px = np.sum(np.diag(probs))
    p2 = np.sum(np.triu(probs, 1))
    p_over_25 = sum(probs[i, j] for i in range(6) for j in range(6) if i + j >= 3)
    return p1, px, p2, p_over_25

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

def update_stats_from_api():
    headers = {"X-Auth-Token": os.environ.get("FOOTBALL_DATA_API_KEY")}
    for code in LEAGUES.keys():
        try:
            url = f"https://api.football-data.org/v4/competitions/{code}/standings"
            data = requests.get(url, headers=headers, timeout=10).json()
            for team_info in data['standings'][0]['table']:
                played = team_info['playedGames']
                if played > 0:
                    supabase.table("teams").upsert({
                        "team_name": team_info['team']['name'],
                        "avg_scored": round(team_info['goalsFor'] / played, 2),
                        "avg_conceded": round(team_info['goalsAgainst'] / played, 2)
                    }, on_conflict="team_name").execute()
            time.sleep(6)
        except: continue

def fetch_and_populate_matches():
    api_key = os.environ.get("ODDS_API_KEY")
    supabase.table("matches").delete().neq("id", 0).execute()
    limit_date = datetime.now(timezone.utc) + timedelta(days=7)
    for code, api_name in LEAGUES.items():
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{api_name}/odds/?apiKey={api_key}&regions=eu&markets=h2h"
            matches = requests.get(url, timeout=15).json()
            for m in matches:
                match_dt = datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                if match_dt < limit_date:
                    supabase.table("matches").insert({
                        "home_team_name": m['home_team'], "away_team_name": m['away_team'],
                        "match_date": m['commence_time'], "status": "scheduled", "league": code
                    }).execute()
            time.sleep(2)
        except: continue

def run_analysis():
    update_stats_from_api()
    fetch_and_populate_matches()
    matches = supabase.table("matches").select("*").execute().data
    stats_map = {s['team_name']: s for s in supabase.table("teams").select("*").execute().data}
    db_team_names = list(stats_map.keys())
    
    report = []
    for m in matches:
        s_h = stats_map.get(find_best_match(m['home_team_name'], db_team_names))
        s_a = stats_map.get(find_best_match(m['away_team_name'], db_team_names))
        
        if s_h and s_a:
            p1, px, p2, p_over = get_full_analysis(s_h['avg_scored'], s_h['avg_conceded'], s_a['avg_scored'], s_a['avg_conceded'], 1.5, 1.2)
            probs_list = sorted([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1], reverse=True)
            best_segno, best_prob = probs_list[0]
            confidenza = best_prob - probs_list[1][1]
            
            if confidenza > 0.05 and best_prob > 0.40: # Filtro sicurezza tarato a 0.05
                report.append(f"📅 *{format_date(m['match_date'])}* - [{m['league']}]\n🏟 {m['home_team_name']} vs {m['away_team_name']}\n🎯 Segno: *{best_segno}* ({round(best_prob*100,1)}%) | Conf: {round(confidenza*100,1)}% | Over 2.5: *{round(p_over*100,1)}%*")

    if report:
        send_telegram_msg("🌍 *ANALISI BIG 5 CON FILTRO SICUREZZA* 🌍\n\n" + "\n\n".join(report[:10]))
    else:
        send_telegram_msg("⚠️ Nessun match a breve termine con alta confidenza trovato.")

if __name__ == "__main__":
    run_analysis()
