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

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

def dixon_coles_correction(i, j, lam_h, lam_a, rho):
    if i == 0 and j == 0: return 1 - (lam_h * lam_a * rho)
    if i == 0 and j == 1: return 1 + (lam_h * rho)
    if i == 1 and j == 0: return 1 + (lam_a * rho)
    if i == 1 and j == 1: return 1 - rho
    return 1.0

def get_full_analysis(att_h, def_h, att_a, def_a):
    # Abbassiamo la media gol per favorire gli Under realistici
    avg_goals = 1.22 
    # Introduciamo il FATTORE CAMPO (+15% attacco casa, -10% difesa casa)
    lam_h = (att_h * 1.15) * (def_a * 1.0) * avg_goals
    lam_a = (att_a * 1.0) * (def_h * 0.90) * avg_goals
    
    rho = -0.15 # Correzione pareggi più marcata
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            base_p = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            probs[i,j] = base_p * dixon_coles_correction(i, j, lam_h, lam_a, rho)
    
    probs /= probs.sum()
    
    p1 = np.sum(np.tril(probs, -1))
    px = np.sum(np.diag(probs))
    p2 = np.sum(np.triu(probs, 1))
    
    # Calcolo accurato Combo Larga
    p_u15 = probs[0,0] + probs[0,1] + probs[1,0]
    p_o15 = 1 - p_u15
    # Somma probabilità fino a 3 gol totali
    p_u35 = sum(probs[i,j] for i in range(6) for j in range(6) if i+j <= 3)
    
    # La combo deve essere quella con probabilità più alta tra le due
    if p_o15 > p_u35:
        combo_label, combo_prob = "O 1.5", p_o15
    else:
        combo_label, combo_prob = "U 3.5", p_u35
    
    return p1, px, p2, combo_label, combo_prob

# 3. RUN
def run_analysis():
    matches = supabase.table("matches").select("*").execute().data
    stats_map = {t['team_name']: t for t in supabase.table("teams").select("*").execute().data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(hours=120)
    results = []

    for m in matches:
        match_time = datetime.fromisoformat(m['match_date'].replace('Z', '+00:00'))
        if match_time < now or match_time > limit_date: continue

        h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=70)
        a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=70)

        if h_res and a_res:
            s_h = stats_map[h_res[0]]
            s_a = stats_map[a_res[0]]
            
            p1, px, p2, combo, c_prob = get_full_analysis(s_h['avg_scored'], s_h['avg_conceded'], s_a['avg_scored'], s_a['avg_conceded'])
            
            # NUOVA LOGICA: Scegliamo il segno più PROBABILE, non quello con più EV
            outcomes = [('1', p1, m['odds_1']), ('X', px, m['odds_x']), ('2', p2, m['odds_2'])]
            # Ordiniamo per probabilità decrescente
            best_choice = max(outcomes, key=lambda x: x[1]) 
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "date": m['match_date'],
                "segno": best_choice[0],
                "prob": best_choice[1],
                "quota": best_choice[2],
                "combo": f"{combo} ({round(c_prob*100)}%)"
            })

    # Ordiniamo i Top 15 per Probabilità Totale (i più sicuri in cima)
    candidates = sorted(results, key=lambda x: x['prob'], reverse=True)
    
    if not candidates:
        send_telegram_msg("⚠️ Nessun match trovato.")
        return

    msg = "🚀 *TOP 15 PRONOSTICI (PRECISIONE PROB.)*\n\n"
    for b in candidates[:15]:
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}\n"
                f"🎯 Fissa: *{b['segno']}* @{b['quota']} (Prob: {round(b['prob']*100)}%)\n"
                f"🛡 Combo: *{b['combo']}*\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
