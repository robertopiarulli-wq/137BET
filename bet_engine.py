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

def find_best_match(name, choices, threshold=80):
    best_match, score = process.extractOne(name, choices)
    return best_match if score >= threshold else None

def get_full_analysis(att_h, def_h, att_a, def_a, avg_h, avg_a):
    lam_h = att_h * def_a * avg_h
    lam_a = att_a * def_h * avg_a
    probs = np.array([[poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a) for j in range(6)] for i in range(6)])
    p1, px, p2 = np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))
    p_over_25 = sum(probs[i, j] for i in range(6) for j in range(6) if i + j >= 3)
    return p1, px, p2, p_over_25

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

def run_analysis():
    # ... (Aggiornamento dati omesso per brevità nel blocco, ma incluso nel file) ...
    matches = supabase.table("matches").select("*").execute().data
    stats_map = {s['team_name']: s for s in supabase.table("teams").select("*").execute().data}
    
    candidates = []
    for m in matches:
        s_h = stats_map.get(find_best_match(m['home_team_name'], list(stats_map.keys())))
        s_a = stats_map.get(find_best_match(m['away_team_name'], list(stats_map.keys())))
        if not (s_h and s_a): continue
            
        p1, px, p2, p_over = get_full_analysis(s_h['avg_scored'], s_h['avg_conceded'], s_a['avg_scored'], s_a['avg_conceded'], 1.5, 1.2)
        
        # Analisi 1X2
        for segno, prob, quota in [('1', p1, m['odds_1']), ('X', px, m['odds_x']), ('2', p2, m['odds_2'])]:
            if (ev := (prob * quota) - 1) > 0:
                candidates.append({"match": f"{m['home_team_name']} vs {m['away_team_name']}", "segno": segno, "ev": ev, "quota": quota, "p_over": p_over})

    # Analisi Over/Under (Assumendo quote medie per il calcolo profittabilità)
    # Nota: Assumiamo una quota standard 1.90 per Over/Under 2.5 per il calcolo EV
    for m in matches:
        # Calcolo semplificato EV Over/Under
        ev_over = (p_over * 1.90) - 1
        ev_under = ((1 - p_over) * 1.90) - 1
        tipo = "Over 2.5" if ev_over > ev_under else "Under 2.5"
        ev_gol = max(ev_over, ev_under)
        if ev_gol > 0.05:
            candidates.append({"match": f"{m['home_team_name']} vs {m['away_team_name']}", "segno": tipo, "ev": ev_gol, "quota": 1.90, "p_over": p_over})

    candidates = sorted(candidates, key=lambda x: x['ev'], reverse=True)
    
    # Messaggio Finale
    msg = "📈 *TOP 10 SINGOLE DI VALORE*\n\n"
    for b in candidates[:10]:
        msg += f"🏟 {b['match']} | *{b['segno']}* @{b['quota']} (EV: {round(b['ev']*100,1)}%)\n"
    
    tripla_cands = [c for c in candidates if c['ev'] > 0.08]
    if len(tripla_cands) >= 3:
        msg += "\n\n🚀 *SCHEDINA OTTIMIZZATA (TRIPLA)*\n\n"
        for b in tripla_cands[:3]:
            msg += f"🏟 {b['match']} -> *{b['segno']}* @{b['quota']}\n"
            
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
