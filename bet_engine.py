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

# --- LOGICA MATEMATICA AVANZATA (V11 QUANTUM) ---

def get_alpha_divergence(team_h, team_a, book_odd):
    """
    Calcola la divergenza basata sulla Costante di Struttura Fine (Alpha)
    Formula: P = 1 / (1 + e^-(alpha * delta_rating + beta))
    """
    if book_odd <= 1.0: return 0, False
    
    alpha = 1 / 137.036
    # Usiamo la differenza di media gol pesata come 'rating'
    rating_h = team_h['avg_scored'] - team_h['avg_conceded']
    rating_a = team_a['avg_scored'] - team_a['avg_conceded']
    delta_rating = (rating_h - rating_a) * 100 # Scaliamo per rendere sensibile l'esponente
    
    beta = 0.12 # Bias per il vantaggio casa
    
    p_quantum = 1 / (1 + np.exp(-(alpha * delta_rating + beta)))
    p_book = 1 / book_odd
    
    divergenza = p_quantum - p_book
    # Alert se la nostra probabilità fisica è superiore al bookmaker di oltre il 7%
    is_value = divergenza > 0.07 
    
    return round(p_quantum * 100), is_value

def get_league_rho(league_code):
    rho_map = {'SA': -0.25, 'FL1': -0.25, 'PL': -0.12, 'BL1': -0.12, 'PD': -0.18}
    return rho_map.get(league_code, -0.20)

def get_motivation_factor(team_data):
    if not team_data.get('recent_form'): return 1.0
    form = team_data['recent_form'].replace(',', '')[-3:]
    if 'W' in form: return 1.05
    if 'L' in form and len(set(form)) == 1: return 0.95
    return 1.0

def get_form_multiplier(form_string):
    if not form_string or form_string == 'DDDDD': return 1.0
    form = form_string.replace(',', '')[-5:].upper()
    points = sum(3 if r == 'W' else 1 if r == 'D' else 0 for r in form)
    multiplier = 1.0 + (points - 7) * 0.03
    return max(0.85, min(1.15, multiplier))

def dixon_coles_tau(i, j, lam_h, lam_a, rho):
    if i == 0 and j == 0: return 1 - (lam_h * lam_a * rho)
    if i == 0 and j == 1: return 1 + (lam_h * rho)
    if i == 1 and j == 0: return 1 + (lam_a * rho)
    if i == 1 and j == 1: return 1 - rho
    return 1.0

def get_full_analysis(team_h, team_a, league_code):
    f_h = get_form_multiplier(team_h.get('recent_form'))
    f_a = get_form_multiplier(team_a.get('recent_form'))
    m_h = get_motivation_factor(team_h)
    m_a = get_motivation_factor(team_a)
    
    avg_goals = 1.25 
    lam_h = (team_h['avg_scored'] * f_h * m_h) * (team_a['avg_conceded'] / f_a) * 1.12 * avg_goals
    lam_a = (team_a['avg_scored'] * f_a * m_a) * (team_h['avg_conceded'] / f_h) * 0.92 * avg_goals
    
    total_xg = lam_h + lam_a
    rho = get_league_rho(league_code)
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p_base = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            probs[i,j] = p_base * dixon_coles_tau(i, j, lam_h, lam_a, rho)
    
    probs /= probs.sum()
    p1, px, p2 = np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))
    
    combo = "U 3.5" if total_xg < 2.5 else "O 1.5"
    c_prob = sum(probs[i,j] for i in range(6) for j in range(6) if (i+j <= 3 if combo == "U 3.5" else i+j >= 2))
    btts = "SÌ" if (lam_h > 1.15 and lam_a > 1.15) else "NO"
    b_prob = 1 - (np.sum(probs[0, :]) + np.sum(probs[:, 0]) - probs[0,0])

    return p1, px, p2, combo, c_prob, btts, b_prob

# --- ENGINE ---
def run_analysis():
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    stats_map = {t['team_name']: t for t in teams_data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(hours=168) 
    results = []
    
    print(f"🧐 DATABASE: {len(matches)} match totali trovati.")
    
    for m in matches:
        m_date_str = m['match_date'].replace(' ', 'T').replace('Z', '')
        if '+' not in m_date_str: m_date_str += '+00:00'
        try:
            match_time = datetime.fromisoformat(m_date_str)
        except: continue
        if match_time < now or match_time > limit_date: continue

        h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=60)
        a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=60)

        if h_res and a_res:
            p1, px, p2, combo, c_prob, btts, b_prob = get_full_analysis(
                stats_map[h_res[0]], stats_map[a_res[0]], m.get('league_code', 'Standard')
            )
            
            best_s = 'X' if px >= 0.27 else max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])[0]
            odd_value = m.get(f'odds_{best_s.lower()}', 1.0)
            
            # CALCOLO DIVERGENZA 137
            p_quantum, is_divergent = get_alpha_divergence(stats_map[h_res[0]], stats_map[a_res[0]], odd_value)
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "date": m['match_date'], "segno": best_s, 
                "prob": px if best_s == 'X' else max(p1, p2),
                "quota": odd_value, "combo": combo, "c_prob": c_prob,
                "btts": btts, "b_prob": b_prob,
                "is_divergent": is_divergent, "p_quantum": p_quantum
            })

    if not results: return

    f_12 = sorted([r for r in results if r['segno'] in ['1', '2']], key=lambda x: x['prob'], reverse=True)[:10]
    f_x = sorted([r for r in results if r['segno'] == 'X'], key=lambda x: x['prob'], reverse=True)[:4]
    final_list = f_12 + f_x

    msg = "🚀 *137BET - POWER REPORT V11*\n"
    msg += f"🏟 _Logica: Dixon-Coles + Regressione Alpha (1/137)_\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    for b in final_list:
        div_label = "⚛️ *DIVERGENZA 137*" if b['is_divergent'] else ""
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']} {div_label}\n"
                f"🎯 Fissa: *{b['segno']}* @{b['quota']} ({round(b['prob']*100)}%)\n"
                f"🛡 Combo: *{b['combo']}* ({round(b['c_prob']*100)}%)\n"
                f"💎 BTTS: *{b['btts']}* ({round(b['b_prob']*100)}%)\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)
    print(f"✅ Analisi V11 Quantistica completata.")

if __name__ == "__main__":
    run_analysis()
