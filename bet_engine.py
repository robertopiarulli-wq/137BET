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

# --- LOGICA QUANTISTICA AVANZATA (V12) ---

def get_quantum_shock_index(team_h, team_a):
    """
    Termometro dello Shock: Usa Alpha come parametro di scala per Poisson.
    Misura l'instabilità infinitesimale tra le due squadre.
    """
    alpha = 1 / 137.036
    # Parametri Lambda 'schiacciati' dalla costante di struttura fine
    lam_h = alpha * (team_h['avg_scored'] + team_a['avg_conceded'])
    lam_a = alpha * (team_a['avg_scored'] + team_h['avg_conceded'])
    
    # Probabilità di 'rottura dello zero' (almeno 1 gol nello stato quantistico)
    p_h = 1 - np.exp(-lam_h)
    p_a = 1 - np.exp(-lam_a)
    
    # Indice di Shock: differenza di potenziale normalizzata su scala 137
    # Più è basso, più il sistema è in equilibrio instabile (pronto a esplodere)
    shock_val = abs(p_h - p_a) * 137
    is_shock = shock_val < 0.05 # Soglia di instabilità critica
    return round(shock_val, 4), is_shock

def get_alpha_divergence(team_h, team_a, book_odd):
    if book_odd <= 1.0: return 0, False
    alpha = 1 / 137.036
    rating_h = team_h['avg_scored'] - team_h['avg_conceded']
    rating_a = team_a['avg_scored'] - team_a['avg_conceded']
    delta_rating = (rating_h - rating_a) * 100 
    beta = 0.12 
    p_quantum = 1 / (1 + np.exp(-(alpha * delta_rating + beta)))
    divergenza = p_quantum - (1 / book_odd)
    return round(p_quantum * 100), divergenza > 0.07

def get_league_rho(league_code):
    rho_map = {'SA': -0.25, 'FL1': -0.25, 'PL': -0.12, 'BL1': -0.12, 'PD': -0.18}
    return rho_map.get(league_code, -0.20)

def get_form_multiplier(form_string):
    if not form_string or form_string == 'DDDDD': return 1.0
    form = form_string.replace(',', '')[-5:].upper()
    points = sum(3 if r == 'W' else 1 if r == 'D' else 0 for r in form)
    return max(0.85, min(1.15, 1.0 + (points - 7) * 0.03))

def get_full_analysis(team_h, team_a, league_code):
    f_h, f_a = get_form_multiplier(team_h.get('recent_form')), get_form_multiplier(team_a.get('recent_form'))
    avg = 1.25
    lam_h = (team_h['avg_scored'] * f_h) * (team_a['avg_conceded'] / f_a) * 1.12 * avg
    lam_a = (team_a['avg_scored'] * f_a) * (team_h['avg_conceded'] / f_h) * 0.92 * avg
    rho = get_league_rho(league_code)
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p_base = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            # Dixon-Coles adjustment
            tau = 1.0
            if i==0 and j==0: tau = 1 - (lam_h*lam_a*rho)
            elif i==0 and j==1: tau = 1 + (lam_h*rho)
            elif i==1 and j==0: tau = 1 + (lam_a*rho)
            elif i==1 and j==1: tau = 1 - rho
            probs[i,j] = p_base * tau
    probs /= probs.sum()
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1)), lam_h+lam_a, probs

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
            p1, px, p2, txG, m_probs = get_full_analysis(t_h, t_a, m.get('league_code', 'Standard'))
            
            best_s = 'X' if px >= 0.27 else max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])[0]
            odd = m.get(f'odds_{best_s.lower()}', 1.0)
            
            # --- CALCOLI QUANTISTICI ---
            _, is_div = get_alpha_divergence(t_h, t_a, odd)
            s_val, is_shock = get_quantum_shock_index(t_h, t_a)
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "date": m['match_date'], "segno": best_s, "prob": px if best_s == 'X' else max(p1, p2),
                "quota": odd, "is_div": is_div, "is_shock": is_shock, "s_val": s_val
            })

    if not results: return
    f_list = sorted([r for r in results if r['segno'] in ['1','2']], key=lambda x: x['prob'], reverse=True)[:10]
    x_list = sorted([r for r in results if r['segno'] == 'X'], key=lambda x: x['prob'], reverse=True)[:4]
    
    msg = "🚀 *137BET V12 - ENTROPIC REPORT*\n"
    msg += "🔬 _Divergenza Alpha + Termometro Shock_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for b in (f_list + x_list):
        tags = ""
        if b['is_div']: tags += " ⚛️"
        if b['is_shock']: tags += " ⚡" # Evento fuori statistica probabile
        
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}{tags}\n"
                f"🎯 Segno: *{b['segno']}* @{b['quota']} ({round(b['prob']*100)}%)\n"
                f"🌡 Shock Index: `{b['s_val']}`\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)
    print("✅ Analisi V12 completata con successo.")

if __name__ == "__main__":
    run_analysis()
