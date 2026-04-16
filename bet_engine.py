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

def save_prediction_137bet(data):
    """Archiviazione automatica per Backtesting Professionale"""
    try:
        supabase.table("prediction_history_137bet").insert({
            "match_name": data['match'],
            "match_date": data['time'],
            "pp_diff": data['pp_diff'],
            "pp_sentenza": data['pp_sentenza'],
            "prob_1": round(data['p1'], 4),
            "prob_x": round(data['px'], 4),
            "prob_2": round(data['p2'], 4),
            "pauli_advice": data['advice'],
            "final_sign_std": data['segno'],
            "stars": data['stars'],
            "home_momentum": data['m_h'],
            "away_momentum": data['m_a']
        }).execute()
    except Exception as e:
        print(f"⚠️ Errore logging database: {e}")

def format_date(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00').replace(' ', 'T'))
        return dt.strftime("%d/%m %H:%M")
    except: return "N.D."

# --- LOGICHE DI PESO ---

def get_momentum_weight(form_string):
    if not form_string: return 1.0
    clean_form = form_string.replace(',', '')[-5:]
    points = sum({'W': 3, 'D': 1, 'L': 0}.get(c, 0) for c in clean_form)
    return round(1 + (points - 7.5) / 50, 3)

def get_defensive_factor(cs_count):
    bonus = (cs_count - 3) * 0.02
    return round(1 - max(-0.15, min(0.15, bonus)), 3)

# --- MOTORE PAULI-PARISI (PP) V17.6 PLATINUM ---

def get_pp_analysis(t_h, t_a):
    def calculate_intensity(stats, is_home):
        p3, g3_f, g3_s = stats.get('p3', 0), stats.get('g3_f', 0), stats.get('g3_s', 0)
        sigma = stats.get('s3', 1.0)
        w_def = 0.8 if is_home else 0.5
        return (p3 + (g3_f * 0.5) - (g3_s * w_def)) / (1 + sigma)

    i_h = calculate_intensity(t_h, True)
    i_a = calculate_intensity(t_a, False)

    if i_h < 0 and i_a < 0:
        delta = i_h + i_a 
    elif (i_h < 0 and i_a >= 0) or (i_h >= 0 and i_a < 0):
        delta = abs(i_h) + abs(i_a)
    else:
        delta = i_h - i_a

    if delta < -6.37:
        sentenza = "🛡️ DOPPIA X-2" if (i_a - i_h) > 4.0 else "🛡️ DOPPIA 1-X"
        return round(delta, 2), sentenza
    elif delta > 6.37:
        sentenza = "🎯 FISSA 2" if i_a > i_h else "🎯 FISSA 1"
        return round(delta, 2), sentenza
    else:
        return round(delta, 2), "🔀 DOPPIA 1-2"

# --- ENGINE QUANTISTICO ---

def get_full_analysis_v17(t_h, t_a):
    m_h, m_a = get_momentum_weight(t_h['recent_form']), get_momentum_weight(t_a['recent_form'])
    def_h, def_a = get_defensive_factor(t_h['clean_sheets']), get_defensive_factor(t_a['clean_sheets'])
    
    alpha = 1 / 137.036
    sigma_q = alpha ** 2
    impact_h = (t_h['avg_scored'] * t_a['avg_conceded']) * m_h
    impact_a = (t_a['goals_scored_away'] * t_h['avg_conceded']) * m_a
    pauli_p = (impact_h * impact_a) * sigma_q * 1000
    
    exclusion = "2" if pauli_p > 0.18 and impact_h > impact_a else "1" if pauli_p > 0.18 else None
    advice = "ECCITATO (ESCLUSIONE)" if pauli_p > 0.18 else "RISONANZA (X ALTA)" if pauli_p < 0.05 else "EQUILIBRIO"
    
    lam_h = (t_h['avg_scored'] * (t_a['avg_conceded'] * def_a)) * m_h * 1.15
    lam_a = (t_a['goals_scored_away'] * (t_h['avg_conceded'] * def_h)) * m_a * 0.90
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            if exclusion == "2" and j > i: p *= 0.03
            if exclusion == "1" and i > j: p *= 0.03
            probs[i,j] = p
    probs /= probs.sum()
    p1, px, p2 = np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))
    return p1, px, p2, pauli_p, advice

# --- CORE ENGINE ---

def run_analysis():
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    stats_map = {t['team_name']: t for t in teams_data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    start_target, end_target = now - timedelta(hours=12), now + timedelta(hours=96)
    results = []

    for m in matches:
        try:
            m_date_str = m['match_date'].replace(' ', 'T').replace('Z', '')
            if '+' not in m_date_str: m_date_str += '+00:00'
            match_time = datetime.fromisoformat(m_date_str)
            if not (start_target <= match_time <= end_target): continue

            h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=45)
            a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=45)

            if h_res and a_res:
                t_h, t_a = stats_map[h_res[0]], stats_map[a_res[0]]
                p1, px, p2, pauli_p, advice = get_full_analysis_v17(t_h, t_a)
                pp_diff, pp_sentenza = get_pp_analysis(t_h, t_a)
                
                outcomes = [('1', p1), ('X', px), ('2', p2)]
                best_s, prob_final = max(outcomes, key=lambda x: x[1])
                stars = "⭐" * min(5, max(1, int(prob_final * 10) - 2)) 
                
                m_h_val = get_momentum_weight(t_h['recent_form'])
                m_a_val = get_momentum_weight(t_a['recent_form'])

                analysis_packet = {
                    "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                    "time": format_date(m['match_date']),
                    "segno": best_s, "p1": p1, "px": px, "p2": p2,
                    "advice": advice, "pp_diff": pp_diff, "pp_sentenza": pp_sentenza,
                    "stars": stars, "m_h": m_h_val, "m_a": m_a_val
                }

                save_prediction_137bet(analysis_packet)
                results.append(analysis_packet)
        except: continue

    if not results: return
    final_list = sorted(results, key=lambda x: max(x['p1'], x['px'], x['p2']), reverse=True)
    
    msg = "🏆 *137BET V17.6 - QUANTUM PARISI MASTER*\n📡 _Fisica del Campo + Asimmetria Baratro_\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for b in final_list:
        h_boost = "📈" if b['m_h'] > 1.05 else "📉" if b['m_h'] < 0.95 else "➖"
        a_boost = "📈" if b['m_a'] > 1.05 else "📉" if b['m_a'] < 0.95 else "➖"
        
        msg += (f"🕒 {b['time']} - {b['match']}\n"
                f"🔥 Fiducia: {b['stars']}\n"
                f"📊 Form: {h_boost} vs {a_boost}\n"
                f"🛡️ Filtro Pauli: *{b['advice']}*\n"
                f"🌀 PP Index: `{b['pp_diff']}`\n"
                f"💡 **SENTENZA PP: {b['pp_sentenza']}**\n"
                f"🎯 Segno STD: *{b['segno']}* ({round(max(b['p1'],b['px'],b['p2'])*100)}%)\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
