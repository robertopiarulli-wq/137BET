import os
import numpy as np
import requests
from scipy.stats import poisson
from supabase import create_client
from thefuzz import process
from datetime import datetime, timedelta, timezone

# --- CONFIGURAZIONE ---
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

def format_date(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00').replace(' ', 'T'))
        return dt.strftime("%d/%m %H:%M")
    except: return "N.D."

# --- LOGICA QUANTISTICA V15.1 (CORRETTA) ---

def get_pauli_v15(team_h, team_a):
    alpha = 1 / 137.036
    sigma = alpha ** 2
    pauli_threshold = 137 * sigma   
    x_pure_threshold = 0.8 * sigma  
    
    impact_h = team_h['avg_scored'] * team_a['avg_conceded']
    impact_a = team_a['avg_scored'] * team_h['avg_conceded']
    pauli_p = (impact_h * impact_a) * sigma * 1000
    
    x_boost, exclusion = 1.0, None
    
    if pauli_p < x_pure_threshold:
        e_level, advice, x_boost = "INDISTINGUIBILE (X PURA)", "RISONANZA: X ALTA", 1.75
    elif pauli_p > pauli_threshold:
        e_level = "ECCITATO (ESCLUSIONE)"
        if impact_h > impact_a:
            exclusion = "2"
            advice = "ESCLUSO SEGNO 2"
        else:
            exclusion = "1"
            advice = "ESCLUSO SEGNO 1"
        x_boost = 0.65
    else:
        e_level, advice = "FONDAMENTALE", "EQUILIBRIO"
        
    return round(pauli_p, 6), e_level, advice, x_boost, exclusion

def get_full_analysis_v15(team_h, team_a):
    avg = 1.25
    lam_h = team_h['avg_scored'] * (team_a['avg_conceded'] / 1.0) * 1.15 * avg
    lam_a = team_a['avg_scored'] * (team_h['avg_conceded'] / 1.0) * 0.90 * avg
    
    _, _, _, x_boost, exclusion = get_pauli_v15(team_h, team_a)
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            if exclusion == "2" and j > i: p *= 0.03 
            if exclusion == "1" and i > j: p *= 0.03 
            if i == j: p *= x_boost
            probs[i,j] = p
            
    probs /= probs.sum()
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

# --- ENGINE DI ANALISI V15.1 CON STORICO ---

def run_analysis():
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    stats_map = {t['team_name']: t for t in teams_data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    start_target = now - timedelta(hours=6)
    end_target = now + timedelta(hours=42)
    
    results = []

    for m in matches:
        m_date_str = m['match_date'].replace(' ', 'T').replace('Z', '')
        if '+' not in m_date_str: m_date_str += '+00:00'
        try: match_time = datetime.fromisoformat(m_date_str)
        except: continue
        
        if not (start_target <= match_time <= end_target): continue

        h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=60)
        a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=60)

        if h_res and a_res:
            t_h, t_a = stats_map[h_res[0]], stats_map[a_res[0]]
            
            if t_h['avg_scored'] == 0 or t_a['avg_scored'] == 0: continue

            p1, px, p2 = get_full_analysis_v15(t_h, t_a)
            pauli_p, level, advice, _, _ = get_pauli_v15(t_h, t_a)
            
            best_s = max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])[0]
            prob_final = px if best_s == 'X' else max(p1, p2)
            
            # --- SALVATAGGIO SU SUPABASE PER IL TRACKING ---
            try:
                supabase.table("predictions_history").insert({
                    "match_name": f"{m['home_team_name']} vs {m['away_team_name']}",
                    "match_date": m['match_date'],
                    "predicted_sign": best_s,
                    "probability": round(float(prob_final), 4),
                    "pauli_p": float(pauli_p)
                }).execute()
            except Exception as e:
                print(f"Errore salvataggio storico: {e}")
            # -----------------------------------------------
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "time": format_date(m['match_date']),
                "segno": best_s, 
                "prob": prob_final,
                "pauli_p": pauli_p, 
                "advice": advice,
                "level": level
            })

    if not results: return

    final_list = sorted(results, key=lambda x: x['prob'], reverse=True)
    
    msg = "🚀 *137BET V15.1 - QUANTUM STREAM*\n"
    msg += "⚛️ _Fix Polarità + Matching 48h_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for b in final_list:
        msg += (f"🕒 {b['time']} - {b['match']}\n"
                f"🎯 Segno: *{b['segno']}* ({round(b['prob']*100)}%)\n"
                f"🛡 Pauli: `{b['advice']}`\n"
                f"💠 P: `{b['pauli_p']}` | `{b['level']}`\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
