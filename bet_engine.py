import os
import numpy as np
import requests
import time
from datetime import datetime, timedelta, timezone
from scipy.stats import poisson
from supabase import create_client
from thefuzz import process

# 1. SETUP
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
LEAGUES = {'SA': 'soccer_italy_serie_a', 'PL': 'soccer_epl', 'PD': 'soccer_spain_la_liga', 'BL1': 'soccer_germany_bundesliga', 'FL1': 'soccer_france_ligue_one'}

# 2. UTILITY
def format_date(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime("%d/%m %H:%M")
    except: return "N.D."

def find_best_match(name, choices, threshold=80):
    best_match, score = process.extractOne(name, choices)
    return best_match if score >= threshold else None

def get_full_analysis(att_h, def_h, att_a, def_a):
    avg_league_goals = 1.35 
    lam_h = att_h * def_a * avg_league_goals
    lam_a = att_a * def_h * avg_league_goals
    
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

# 3. ANALYSIS
def run_analysis():
    update_stats_from_api()
    fetch_and_populate_matches()
    
    matches = supabase.table("matches").select("*").execute().data
    stats_map = {s['team_name']: s for s in supabase.table("teams").select("*").execute().data}
    
    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(hours=120)
    
    best_signs_by_match = {}
    
    for m in matches:
        match_time = datetime.fromisoformat(m['match_date'].replace('Z', '+00:00'))
        if match_time < now or match_time > limit_date:
            continue

        s_h = stats_map.get(find_best_match(m['home_team_name'], list(stats_map.keys())))
        s_a = stats_map.get(find_best_match(m['away_team_name'], list(stats_map.keys())))
        if not (s_h and s_a): continue
            
        p1, px, p2, p_over = get_full_analysis(s_h['avg_scored'], s_h['avg_conceded'], s_a['avg_scored'], s_a['avg_conceded'])
        
        match_name = f"{m['home_team_name']} vs {m['away_team_name']}"
        dc_options = [('1X', p1 + px), ('X2', px + p2), ('12', p1 + p2)]
        best_dc = max(dc_options, key=lambda x: x[1])[0]
        best_ou = "Over 2.5" if p_over > 0.50 else "Under 2.5"
        
        possible_bets = [('1', p1, m['odds_1']), ('X', px, m['odds_x']), ('2', p2, m['odds_2'])]
        best_ev = -1.0
        best_data = None
        
        for segno, prob, quota in possible_bets:
            ev = (prob * quota) - 1
            if ev > best_ev:
                best_ev = ev
                best_data = {
                    "match": match_name, "segno": segno, "ev": ev, "quota": quota, 
                    "date": m['match_date'], "dc": best_dc, "ou": f"{best_ou} ({round(p_over*100)}%)"
                }
        
        if best_ev > 0:
            best_signs_by_match[match_name] = best_data

    candidates = sorted(best_signs_by_match.values(), key=lambda x: x['ev'], reverse=True)
    
    if not candidates:
        send_telegram_msg("⚠️ Nessun match trovato nei prossimi 5 giorni.")
        return

    msg = "📊 *TOP 15 ANALISI COMPLETE (120H)*\n\n"
    for b in candidates[:15]:
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}\n"
                f"🎯 Fissa: *{b['segno']}* @{b['quota']} (EV: {round(b['ev']*100,1)}%)\n"
                f"🛡 Doppia: *{b['dc']}* | ⚽️ *{b['ou']}*\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
