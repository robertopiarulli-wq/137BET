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
        return dt.strftime("%H:%M")
    except: return "N.D."

# --- LOGICA QUANTISTICA V15 (DAILY STREAM) ---

def get_pauli_v15(team_h, team_a):
    """V15: Ottimizzata per Big 5 + Serie Cadette"""
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
        exclusion = "2" if impact_h > impact_a else "1"
        advice, x_boost = f"ESCLUSO SEGNO {exclusion}", 0.65
    else:
        e_level, advice = "FONDAMENTALE", "EQUILIBRIO STANDARD"
        
    return round(pauli_p, 6), e_level, advice, x_boost, exclusion

def get_full_analysis_v15(team_h, team_a):
    """Dixon-Coles V15 con Salto Quantistico Radicale"""
    avg = 1.25
    lam_h = team_h['avg_scored'] * (team_a['avg_conceded'] / 1.0) * 1.15 * avg
    lam_a = team_a['avg_scored'] * (team_h['avg_conceded'] / 1.0) * 0.90 * avg
    
    _, _, _, x_boost, exclusion = get_pauli_v15(team_h, team_a)
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            # Salto Quantistico: Svuotamento quasi totale degli stati proibiti (3%)
            if exclusion == "2" and j > i: p *= 0.03 
            if exclusion == "1" and i > j: p *= 0.03 
            if i == j: p *= x_boost
            probs[i,j] = p
            
    probs /= probs.sum()
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

# --- ENGINE DI ANALISI V15 ---

def run_analysis():
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    stats_map = {t['team_name']: t for t in teams_data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    # Target: Solo i match di domani (Daily Stream)
    start_target = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
    end_target = start_target + timedelta(hours=23, minutes=59)
    
    results = []

    for m in matches:
        m_date_str = m['match_date'].replace(' ', 'T').replace('Z', '')
        if '+' not in m_date_str: m_date_str += '+00:00'
        try: match_time = datetime.fromisoformat(m_date_str)
        except: continue
        
        # Filtro Daily V15
        if not (start_target <= match_time <= end_target): continue

        h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=70)
        a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=70)

        if h_res and a_res:
            t_h, t_a = stats_map[h_res[0]], stats_map[a_res[0]]
            p1, px, p2 = get_full_analysis_v15(t_h, t_a)
            pauli_p, level, advice, _, _ = get_pauli_v15(t_h, t_a)
            
            best_s = max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])[0]
            prob_final = px if best_s == 'X' else max(p1, p2)
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "time": match_time.strftime("%H:%M"),
                "segno": best_s, 
                "prob": prob_final,
                "quota": m.get(f'odds_{best_s.lower()}', 1.0),
                "pauli_p": pauli_p, 
                "advice": advice,
                "level": level
            })

    if not results: return

    # Ordinamento Totale per Probabilità (Nessun limite di 14)
    final_list = sorted(results, key=lambda x: x['prob'], reverse=True)
    
    msg = f"📅 *STREAM QUANTISTICO: {start_target.strftime('%d/%m')}*\n"
    msg += "⚛️ _V15 GOLD: Big 5 + Serie Cadette_\n"
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
