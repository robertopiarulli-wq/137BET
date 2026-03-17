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

def get_full_analysis(att_h, def_h, att_a, def_a):
    # Costante correttiva per evitare l'inflazione dei gol
    # 1.15 è una media prudente che favorisce la comparsa di Under e Pareggi
    base = 1.15 
    
    lam_h = att_h * def_a * base
    lam_a = att_a * def_h * base
    
    # Generazione matrice 6x6
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            probs[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
    
    p1 = np.sum(np.tril(probs, -1)) # Casa vince
    px = np.sum(np.diag(probs))     # Pareggio
    p2 = np.sum(np.triu(probs, 1))  # Ospite vince
    
    # Calcolo Over 2.5 rigoroso
    p_under_25 = probs[0,0] + probs[0,1] + probs[0,2] + probs[1,0] + probs[1,1] + probs[2,0]
    p_over = 1 - p_under_25
    
    return p1, px, p2, p_over

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

def run_analysis():
    # Recupero dati
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    stats_map = {t['team_name']: t for t in teams_data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(hours=120)
    results = []

    for m in matches:
        match_time = datetime.fromisoformat(m['match_date'].replace('Z', '+00:00'))
        if match_time < now or match_time > limit_date: continue

        # Matching nomi squadre
        h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=70)
        a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=70)

        if h_res and a_res:
            s_h = stats_map[h_res[0]]
            s_a = stats_map[a_res[0]]
            
            p1, px, p2, p_over = get_full_analysis(s_h['avg_scored'], s_h['avg_conceded'], s_a['avg_scored'], s_a['avg_conceded'])
            
            # Determinazione Doppia Chance (la più probabile)
            dc_map = {'1X': p1 + px, 'X2': px + p2, '12': p1 + p2}
            best_dc = max(dc_map, key=dc_map.get)
            
            # Determinazione Over/Under (soglia 50%)
            ou_label = "Over 2.5" if p_over > 0.50 else "Under 2.5"
            
            # Scelta del segno con EV maggiore
            outcomes = [('1', p1, m['odds_1']), ('X', px, m['odds_x']), ('2', p2, m['odds_2'])]
            best_ev = -999
            selected = None
            
            for segno, prob, quota in outcomes:
                ev = (prob * quota) - 1
                if ev > best_ev:
                    best_ev = ev
                    selected = (segno, quota)

            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "date": m['match_date'],
                "segno": selected[0], "quota": selected[1], "ev": best_ev,
                "dc": best_dc, "ou": f"{ou_label} ({round(p_over*100)}%)"
            })

    # Ordiniamo per EV decrescente
    candidates = sorted(results, key=lambda x: x['ev'], reverse=True)
    
    if not candidates:
        send_telegram_msg("⚠️ Nessun match trovato.")
        return

    msg = "📊 *TOP 15 ANALISI (STIME RICALIBRATE)*\n\n"
    for b in candidates[:15]:
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}\n"
                f"🎯 Fissa: *{b['segno']}* @{b['quota']} (EV: {round(b['ev']*100,1)}%)\n"
                f"🛡 Doppia: *{b['dc']}* | ⚽️ *{b['ou']}*\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
