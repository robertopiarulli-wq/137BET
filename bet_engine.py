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
    except: return "N.D."

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

def run_analysis():
    # Recupero dati da Supabase
    matches = supabase.table("matches").select("*").execute().data
    stats_map = {s['team_name']: s for s in supabase.table("teams").select("*").execute().data}
    
    best_signs_by_match = {}
    
    for m in matches:
        s_h = stats_map.get(find_best_match(m['home_team_name'], list(stats_map.keys())))
        s_a = stats_map.get(find_best_match(m['away_team_name'], list(stats_map.keys())))
        if not (s_h and s_a): continue
            
        p1, px, p2, p_over = get_full_analysis(s_h['avg_scored'], s_h['avg_conceded'], s_a['avg_scored'], s_a['avg_conceded'], 1.5, 1.2)
        
        # Logica Doppia Chance (prende la coppia con probabilità maggiore)
        dc_options = [('1X', p1 + px), ('X2', px + p2), ('12', p1 + p2)]
        best_dc = max(dc_options, key=lambda x: x[1])[0]
        
        # Logica Over/Under
        best_ou = "Over 2.5" if p_over > 0.52 else "Under 2.5"
        
        # Scelta della Fissa con EV migliore
        possible_bets = [('1', p1, m['odds_1']), ('X', px, m['odds_x']), ('2', p2, m['odds_2'])]
        
        match_name = f"{m['home_team_name']} vs {m['away_team_name']}"
        best_ev = -1.0
        best_data = None
        
        for segno, prob, quota in possible_bets:
            ev = (prob * quota) - 1
            if ev > best_ev:
                best_ev = ev
                best_data = {
                    "match": match_name, "segno": segno, "ev": ev, "quota": quota, 
                    "date": m['match_date'], "dc": best_dc, "ou": best_ou
                }
        
        if best_ev > 0:
            best_signs_by_match[match_name] = best_data

    candidates = sorted(best_signs_by_match.values(), key=lambda x: x['ev'], reverse=True)
    
    # Costruzione Messaggio
    msg = "📊 *ANALISI COMPLETA DEL GIORNO*\n\n"
    for b in candidates[:10]:
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}\n"
                f"🎯 Fissa: *{b['segno']}* @{b['quota']} (EV: {round(b['ev']*100,1)}%)\n"
                f"🛡 Doppia: *{b['dc']}* | ⚽️ *{b['ou']}*\n"
                f"────────────────\n")
    
    if len(candidates) >= 3:
        msg += "\n🚀 *TRIPLA OTTIMIZZATA*\n"
        for b in candidates[:3]:
            msg += f"• {b['match']} -> *{b['segno']}*\n"
    
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
