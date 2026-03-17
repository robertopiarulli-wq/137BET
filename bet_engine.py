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

def format_date(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime("%d/%m %H:%M")
    except: return "N.D."

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

def dixon_coles_tau(i, j, lam_h, lam_a, rho):
    if i == 0 and j == 0: return 1 - (lam_h * lam_a * rho)
    if i == 0 and j == 1: return 1 + (lam_h * rho)
    if i == 1 and j == 0: return 1 + (lam_a * rho)
    if i == 1 and j == 1: return 1 - rho
    return 1.0

def get_full_analysis(att_h, def_h, att_a, def_a):
    avg_goals = 1.25 
    lam_h = (att_h * 1.12) * (def_a * 0.95) * avg_goals
    lam_a = (att_a * 0.92) * (def_h * 1.05) * avg_goals
    rho = -0.20 
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p_base = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            probs[i,j] = p_base * dixon_coles_tau(i, j, lam_h, lam_a, rho)
    
    probs /= probs.sum()
    
    p1, px, p2 = np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))
    
    # Combo Larga
    p_u35 = sum(probs[i,j] for i in range(6) for j in range(6) if i+j <= 3)
    p_o15 = 1 - (probs[0,0] + probs[0,1] + probs[1,0])
    
    combo, c_prob = ("U 3.5", p_u35) if p_u35 > 0.60 else ("O 1.5", p_o15)
    return p1, px, p2, combo, c_prob

def run_analysis():
    matches = supabase.table("matches").select("*").execute().data
    stats_map = {t['team_name']: t for t in supabase.table("teams").select("*").execute().data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(hours=120)
    results = []
    
    # Contatori per statistiche LOG
    stats_log = {"1": 0, "X": 0, "2": 0, "O 1.5": 0, "U 3.5": 0}

    for m in matches:
        match_time = datetime.fromisoformat(m['match_date'].replace('Z', '+00:00'))
        if match_time < now or match_time > limit_date: continue

        h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=70)
        a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=70)

        if h_res and a_res:
            p1, px, p2, combo, c_prob = get_full_analysis(stats_map[h_res[0]]['avg_scored'], stats_map[h_res[0]]['avg_conceded'], 
                                                          stats_map[a_res[0]]['avg_scored'], stats_map[a_res[0]]['avg_conceded'])
            
            # Segno: se la X è > 27% la forziamo per vederla, altrimenti il più probabile
            best_s = 'X' if px >= 0.27 else max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])[0]
            
            # Aggiorna statistiche globali per il log
            stats_log[best_s] += 1
            stats_log[combo] += 1

            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "date": m['match_date'], "segno": best_s, "prob": px if best_s == 'X' else max(p1, p2),
                "quota": m[f'odds_{best_s.lower()}'], "combo": f"{combo} ({round(c_prob*100)}%)"
            })

    # --- LOG STATISTICO SU GITHUB ---
    total_analyzed = len(results)
    print(f"\n--- REPORT STATISTICO ANALISI ({total_analyzed} match) ---")
    print(f"Segni suggeriti: 1: {stats_log['1']} | X: {stats_log['X']} | 2: {stats_log['2']}")
    print(f"Combo suggerite: O 1.5: {stats_log['O 1.5']} | U 3.5: {stats_log['U 3.5']}")
    print("-------------------------------------------\n")

    candidates = sorted(results, key=lambda x: x['prob'], reverse=True)
    
    if not candidates:
        send_telegram_msg("⚠️ Nessun match trovato.")
        return

    msg = "🔬 *ANALISI DIXON-COLES (TOP 15)*\n\n"
    for b in candidates[:15]:
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}\n"
                f"🎯 Fissa: *{b['segno']}* @{b['quota']}\n"
                f"🛡 Combo: *{b['combo']}*\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
