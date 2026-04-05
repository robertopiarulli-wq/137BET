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

# --- LOGICA QUANTISTICA V13 (PAULI EXCLUSION) ---

def get_pauli_exclusion_factor(team_h, team_a):
    """
    V13: Introduce la Costante di Pauli come prodotto dei risultati.
    Determina se uno stato (es. il pareggio) è fisicamente 'escluso'.
    """
    alpha = 1 / 137.036
    pauli_sigma = alpha ** 2 # Costante di interazione del secondo ordine
    
    # Forza d'urto del match (Prodotto delle intensità)
    impact_h = team_h['avg_scored'] * team_a['avg_conceded']
    impact_a = team_a['avg_scored'] * team_h['avg_conceded']
    
    # Il prodotto di Pauli: misura l'interferenza tra i due stati
    pauli_product = (impact_h * impact_a) * pauli_sigma * 1000
    
    # Se il prodotto è troppo alto, gli stati 'collassano': il pareggio diventa meno ammissibile
    exclusion_level = "ECCITATO" if pauli_product > 0.5 else "FONDAMENTALE"
    
    # Moltiplicatore di esclusione per il segno X
    # Più è alto il prodotto, più il pareggio viene 'spinto fuori' dal sistema
    x_exclusion = np.exp(-pauli_product)
    
    return round(pauli_product, 6), exclusion_level, x_exclusion

def get_quantum_shock_index(team_h, team_a):
    alpha = 1 / 137.036
    lam_h = alpha * (team_h['avg_scored'] + team_a['avg_conceded'])
    lam_a = alpha * (team_a['avg_scored'] + team_h['avg_conceded'])
    p_h, p_a = 1 - np.exp(-lam_h), 1 - np.exp(-lam_a)
    shock_val = abs(p_h - p_a) * 137
    return round(shock_val, 4), shock_val < 0.137, ("1" if p_h > p_a else "2")

def get_alpha_divergence(team_h, team_a, book_odd):
    if book_odd <= 1.0: return 0, False
    alpha = 1 / 137.036
    rating_h = team_h['avg_scored'] - team_h['avg_conceded']
    rating_a = team_a['avg_scored'] - team_a['avg_conceded']
    delta_rating = (rating_h - rating_a) * 100 
    p_quantum = 1 / (1 + np.exp(-(alpha * delta_rating + 0.12)))
    return round(p_quantum * 100), (p_quantum - (1 / book_odd)) > 0.07

def get_full_analysis(team_h, team_a, league_code):
    # Dixon-Coles Base
    avg = 1.25
    lam_h = team_h['avg_scored'] * (team_a['avg_conceded'] / 1.0) * 1.12 * avg
    lam_a = team_a['avg_scored'] * (team_h['avg_conceded'] / 1.0) * 0.92 * avg
    
    # Applicazione Prodotto di Pauli
    _, _, x_mod = get_pauli_exclusion_factor(team_h, team_a)
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            # Se è un pareggio (i == j), applichiamo l'esclusione di Pauli
            if i == j: p *= x_mod
            probs[i,j] = p
            
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
            p1, px, p2 = get_full_analysis(t_h, t_a, m.get('league_code', 'Standard'))
            
            # Pauli Insights
            p_val, e_level, _ = get_pauli_exclusion_factor(t_h, t_a)
            
            best_s = 'X' if px >= 0.27 else max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])[0]
            odd = m.get(f'odds_{best_s.lower()}', 1.0)
            
            _, is_div = get_alpha_divergence(t_h, t_a, odd)
            s_val, is_shock, s_dir = get_quantum_shock_index(t_h, t_a)
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "date": m['match_date'], "segno": best_s, "prob": px if best_s == 'X' else max(p1, p2),
                "quota": odd, "is_div": is_div, "is_shock": is_shock, "s_val": s_val, "s_dir": s_dir,
                "pauli_p": p_val, "e_level": e_level
            })

    if not results: return
    f_list = sorted([r for r in results if r['segno'] in ['1','2']], key=lambda x: x['prob'], reverse=True)[:10]
    x_list = sorted([r for r in results if r['segno'] == 'X'], key=lambda x: x['prob'], reverse=True)[:4]
    
    msg = "🚀 *137BET V13 - EXCLUSION EDITION*\n"
    msg += "⚛️ _Logica: Pauli Principle + Alpha Product_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for b in (f_list + x_list):
        tags = ""
        if b['is_div']: tags += " ⚛️"
        if b['is_shock']: tags += f" ⚡ SQUILIBRIO: {b['s_dir']}" 
        
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}{tags}\n"
                f"🎯 Segno: *{b['segno']}* @{b['quota']} ({round(b['prob']*100)}%)\n"
                f"💠 Stato: `{b['e_level']}` | Pauli P: `{b['pauli_p']}`\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)
    print("✅ Analisi V13 completata.")

if __name__ == "__main__":
    run_analysis()
