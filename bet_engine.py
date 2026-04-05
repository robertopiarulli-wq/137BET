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

# --- LOGICA QUANTISTICA V14 (ZERO-POINT ENERGY) ---

def get_pauli_v14(team_h, team_a):
    """
    V14: Logica di Indistinguibilità per il rimbalzo delle X.
    Implementa il Salto Quantistico e lo Zero-Point Energy.
    """
    alpha = 1 / 137.036
    sigma = alpha ** 2
    pauli_threshold = 137 * sigma   # Soglia Eccitazione (~0.007)
    x_pure_threshold = 0.8 * sigma  # Soglia Indistinguibilità (X Pura)
    
    # Calcolo impatto basato su medie storiche
    impact_h = team_h['avg_scored'] * team_a['avg_conceded']
    impact_a = team_a['avg_scored'] * team_h['avg_conceded']
    
    # Prodotto di Pauli (L'energia di interazione)
    pauli_p = (impact_h * impact_a) * sigma * 1000
    
    x_boost = 1.0
    exclusion = None
    
    if pauli_p < x_pure_threshold:
        e_level = "INDISTINGUIBILE (X PURA)"
        advice = "RISONANZA: X ALTA PROBABILITÀ"
        x_boost = 1.65  # Forte rimbalzo per le X pure
    elif pauli_p > pauli_threshold:
        e_level = "ECCITATO (ESCLUSIONE)"
        exclusion = "2" if impact_h > impact_a else "1"
        advice = f"ESCLUSO SEGNO {exclusion}"
        x_boost = 0.70  # La X decade: lo stato è troppo instabile
    else:
        e_level = "FONDAMENTALE"
        advice = "EQUILIBRIO STANDARD"
        
    return round(pauli_p, 6), e_level, advice, x_boost, exclusion

def get_quantum_shock_index(team_h, team_a):
    """Indice di Shock per identificare eventi fuori statistica"""
    alpha = 1 / 137.036
    lam_h = alpha * (team_h['avg_scored'] + team_a['avg_conceded'])
    lam_a = alpha * (team_a['avg_scored'] + team_h['avg_conceded'])
    p_h, p_a = 1 - np.exp(-lam_h), 1 - np.exp(-lam_a)
    shock_val = abs(p_h - p_a) * 137
    return round(shock_val, 4), shock_val < 0.137, ("1" if p_h > p_a else "2")

def get_full_analysis_v14(team_h, team_a):
    """Dixon-Coles potenziato dal Salto Quantistico di Pauli"""
    avg = 1.25
    lam_h = team_h['avg_scored'] * (team_a['avg_conceded'] / 1.0) * 1.12 * avg
    lam_a = team_a['avg_scored'] * (team_h['avg_conceded'] / 1.0) * 0.92 * avg
    
    # Otteniamo i parametri Pauli V14
    _, _, _, x_boost, exclusion = get_pauli_v14(team_h, team_a)
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            
            # SALTO QUANTISTICO: Se uno stato è escluso, l'energia decade
            if exclusion == "2" and j > i: p *= 0.05 # Quasi impossibile la vittoria ospite
            if exclusion == "1" and i > j: p *= 0.05 # Quasi impossibile la vittoria casa
            
            # RIMBALZO X: Se le forze sono indistinguibili
            if i == j: p *= x_boost
            
            probs[i,j] = p
            
    probs /= probs.sum()
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

# --- ENGINE DI ANALISI ---

def run_analysis():
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    stats_map = {t['team_name']: t for t in teams_data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(hours=168)
    results = []

    for m in matches:
        # Parsing data
        m_date_str = m['match_date'].replace(' ', 'T').replace('Z', '')
        if '+' not in m_date_str: m_date_str += '+00:00'
        try: match_time = datetime.fromisoformat(m_date_str)
        except: continue
        
        if match_time < now or match_time > limit_date: continue

        # Matching nomi squadre
        h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=60)
        a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=60)

        if h_res and a_res:
            t_h, t_a = stats_map[h_res[0]], stats_map[a_res[0]]
            
            # Analisi V14
            p1, px, p2 = get_full_analysis_v14(t_h, t_a)
            pauli_p, e_level, advice, _, _ = get_pauli_v14(t_h, t_a)
            s_val, is_shock, s_dir = get_quantum_shock_index(t_h, t_a)
            
            # Selezione segno dominante dopo distorsione
            best_s = max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])[0]
            prob_final = px if best_s == 'X' else max(p1, p2)
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "date": m['match_date'], 
                "segno": best_s, 
                "prob": prob_final,
                "quota": m.get(f'odds_{best_s.lower()}', 1.0),
                "pauli_p": pauli_p, 
                "e_level": e_level, 
                "advice": advice,
                "is_shock": is_shock,
                "s_dir": s_dir
            })

    if not results:
        print("Nessun match trovato per l'analisi.")
        return

    # Generazione Report Ordinata per Probabilità Quantistica
    final_list = sorted(results, key=lambda x: x['prob'], reverse=True)[:14]
    
    msg = "🚀 *137BET V14 - ZERO-POINT ENERGY*\n"
    msg += "⚛️ _Salto Quantistico + Rimbalzo X pura_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for b in final_list:
        shock_tag = f" ⚡ SQUILIBRIO: {b['s_dir']}" if b['is_shock'] else ""
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}{shock_tag}\n"
                f"🎯 Segno: *{b['segno']}* @{b['quota']} ({round(b['prob']*100)}%)\n"
                f"🌀 Pauli: `{b['advice']}`\n"
                f"✨ Stato: `{b['e_level']}` | `{b['pauli_p']}`\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)
    print("✅ Analisi V14 completata e inviata.")

if __name__ == "__main__":
    run_analysis()
