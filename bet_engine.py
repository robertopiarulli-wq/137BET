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

# --- LOGICA QUANTISTICA V13.1 (PAULI SENSITIVITY) ---

def get_pauli_logic(team_h, team_a):
    """
    V13.1: Usa 137 * sigma come soglia di eccitazione.
    Gestisce l'esclusione del segno o l'indeterminazione (X).
    """
    alpha = 1 / 137.036
    sigma = alpha ** 2
    # NUOVA SOGLIA SENSIBILE: 137 * sigma
    pauli_threshold = 137 * sigma 
    
    impact_h = team_h['avg_scored'] * team_a['avg_conceded']
    impact_a = team_a['avg_scored'] * team_h['avg_conceded']
    
    # Prodotto di Risultato
    pauli_p = (impact_h * impact_a) * sigma * 1000
    
    # Determinazione dello Stato
    if pauli_p > pauli_threshold:
        e_level = "ECCITATO"
        # Esclusione del segno opposto: pende verso il potenziale maggiore
        exclusion_target = "2" if impact_h > impact_a else "1"
        pauli_advice = f"ESCLUSO SEGNO {exclusion_target}"
    else:
        e_level = "INDETERMINATO"
        # Se non c'è abbastanza energia per escludere, la X è lo stato stabile
        pauli_advice = "PROPOSTA X (NON ESCLUDIBILE)"
        
    return round(pauli_p, 6), e_level, pauli_advice

def get_quantum_shock_index(team_h, team_a):
    alpha = 1 / 137.036
    lam_h = alpha * (team_h['avg_scored'] + team_a['avg_conceded'])
    lam_a = alpha * (team_a['avg_scored'] + team_h['avg_conceded'])
    p_h, p_a = 1 - np.exp(-lam_h), 1 - np.exp(-lam_a)
    shock_val = abs(p_h - p_a) * 137
    return round(shock_val, 4), shock_val < 0.137, ("1" if p_h > p_a else "2")

def get_full_analysis(team_h, team_a):
    avg = 1.25
    lam_h = team_h['avg_scored'] * (team_a['avg_conceded'] / 1.0) * 1.12 * avg
    lam_a = team_a['avg_scored'] * (team_h['avg_conceded'] / 1.0) * 0.92 * avg
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            probs[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            
    probs /= probs.sum()
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

# --- ENGINE ---
def run_analysis():
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    stats_map = {t['team_name']: t for t in teams_data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(hours=168)
    results = []

    for m in matches:
        m_date_str = m['match_date'].replace(' ', 'T').replace('Z', '')
        if '+' not in m_date_str: m_date_str += '+00:00'
        try: match_time = datetime.fromisoformat(m_date_str)
        except: continue
        if match_time < now or match_time > limit_date: continue

        h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=60)
        a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=60)

        if h_res and a_res:
            t_h, t_a = stats_map[h_res[0]], stats_map[a_res[0]]
            p1, px, p2 = get_full_analysis(t_h, t_a)
            
            # NUOVA LOGICA PAULI V13.1
            pauli_p, e_level, pauli_advice = get_pauli_logic(t_h, t_a)
            
            # Se Pauli propone X, forziamo il segno
            if "PROPOSTA X" in pauli_advice:
                best_s = "X"
                prob_val = px
            else:
                best_s = max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])[0]
                prob_val = px if best_s == 'X' else max(p1, p2)
            
            odd = m.get(f'odds_{best_s.lower()}', 1.0)
            s_val, is_shock, s_dir = get_quantum_shock_index(t_h, t_a)
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "date": m['match_date'], "segno": best_s, "prob": prob_val,
                "quota": odd, "is_shock": is_shock, "s_dir": s_dir,
                "pauli_p": pauli_p, "e_level": e_level, "advice": pauli_advice
            })

    if not results: return
    final_list = sorted(results, key=lambda x: x['prob'], reverse=True)[:14]
    
    msg = "🚀 *137BET V13.1 - PAULI SENSITIVITY*\n"
    msg += "⚛️ _Soglia: 137*sigma | Logica di Esclusione_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for b in final_list:
        shock_tag = f" ⚡ SQUILIBRIO: {b['s_dir']}" if b['is_shock'] else ""
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}{shock_tag}\n"
                f"🎯 Segno: *{b['segno']}* @{b['quota']} ({round(b['prob']*100)}%)\n"
                f"🛡 Pauli: `{b['advice']}`\n"
                f"💠 Pauli P: `{b['pauli_p']}` | `{b['e_level']}`\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)
    print("✅ Analisi V13.1 completata con successo.")

if __name__ == "__main__":
    run_analysis()
