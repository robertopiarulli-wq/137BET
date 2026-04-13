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

# --- LOGICHE DI PESO V17.1 ---

def get_momentum_weight(form_string):
    if not form_string: return 1.0
    clean_form = form_string.replace(',', '')[-5:]
    points = sum({'W': 3, 'D': 1, 'L': 0}.get(c, 0) for c in clean_form)
    return round(1 + (points - 7.5) / 50, 3)

def get_defensive_factor(cs_count):
    bonus = (cs_count - 3) * 0.02
    return round(1 - max(-0.15, min(0.15, bonus)), 3)

# --- NUOVO MOTORE PAULI-PARISI (PP) ---

def get_pp_analysis(t_h, t_a):
    """
    Calcola il differenziale Parisi basato su Intensità (I) e Rugosità (Sigma)
    Considerando Punti, Gol Fatti e Gol Subiti pesati (Casa 0.8 / Trasferta 0.5)
    """
    def calculate_intensity(stats, is_home):
        # DeltaH (Punti ultime 3), Lambda_f (Gol fatti), Lambda_s (Gol subiti), Sigma (Rugosità)
        # Nota: Questi dati devono essere estratti dal DB (colonne p3, g3_f, g3_s, s3)
        p3 = stats.get('p3', 4.5) # Default media se manca dato
        g3_f = stats.get('g3_f', 1.5)
        g3_s = stats.get('g3_s', 1.5)
        sigma = stats.get('s3', 1.0) # 0=Stabile, 1=Misto, 1.5=Instabile
        
        w_def = 0.8 if is_home else 0.5
        
        # Formula Parisi: I = (Punti + (GolF * 0.5) - (GolS * W_def)) / (1 + Sigma)
        intensity = (p3 + (g3_f * 0.5) - (g3_s * w_def)) / (1 + sigma)
        return intensity

    i_h = calculate_intensity(t_h, True)
    i_a = calculate_intensity(t_a, False)
    diff = round(i_h - i_a, 2)
    
    if diff >= 6.37:
        return diff, "🎯 FISSA"
    elif -6.37 < diff < 6.37:
        return diff, "🔀 DOPPIA 1-2"
    else: # diff <= -6.37
        return diff, "🛡️ DOPPIA 1-X"

# --- ENGINE DI ANALISI QUANTISTICA V17.1 (CON ESCLUSIONE) ---

def get_pauli_analysis_v17(t_h, t_a):
    alpha = 1 / 137.036
    sigma = alpha ** 2
    
    m_h, m_a = get_momentum_weight(t_h['recent_form']), get_momentum_weight(t_a['recent_form'])
    
    impact_h = (t_h['avg_scored'] * t_a['avg_conceded']) * m_h
    impact_a = (t_a['goals_scored_away'] * t_h['avg_conceded']) * m_a
    
    pauli_p = (impact_h * impact_a) * sigma * 1000
    
    exclusion = None
    advice = "EQUILIBRIO"
    
    if pauli_p > 0.18:
        advice = "ECCITATO (ESCLUSIONE)"
        exclusion = "2" if impact_h > impact_a else "1"
    elif pauli_p < 0.05:
        advice = "RISONANZA (X ALTA)"
        
    return round(pauli_p, 6), exclusion, advice

def get_full_analysis_v17(t_h, t_a):
    m_h, m_a = get_momentum_weight(t_h['recent_form']), get_momentum_weight(t_a['recent_form'])
    def_h, def_a = get_defensive_factor(t_h['clean_sheets']), get_defensive_factor(t_a['clean_sheets'])
    
    lam_h = (t_h['avg_scored'] * (t_a['avg_conceded'] * def_a)) * m_h * 1.15
    lam_a = (t_a['goals_scored_away'] * (t_h['avg_conceded'] * def_h)) * m_a * 0.90
    
    pauli_p, exclusion, advice = get_pauli_analysis_v17(t_h, t_a)
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            if exclusion == "2" and j > i: p *= 0.03
            if exclusion == "1" and i > j: p *= 0.03
            probs[i,j] = p
            
    probs /= probs.sum()
    
    p1 = np.sum(np.tril(probs, -1))
    px = np.sum(np.diag(probs))
    p2 = np.sum(np.triu(probs, 1))
    
    return p1, px, p2, pauli_p, advice

# --- CORE ENGINE ---

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

            p1, px, p2, pauli_p, advice = get_full_analysis_v17(t_h, t_a)
            
            # Calcolo PP (Parisi)
            pp_diff, pp_sentenza = get_pp_analysis(t_h, t_a)
            
            outcomes = [('1', p1), ('X', px), ('2', p2)]
            best_s, prob_final = max(outcomes, key=lambda x: x[1])
            stars = min(5, max(1, int(prob_final * 10) - 2)) 
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "time": format_date(m['match_date']),
                "segno": best_s, 
                "prob": prob_final,
                "pauli_p": pauli_p,
                "advice": advice,
                "pp_diff": pp_diff,
                "pp_sentenza": pp_sentenza,
                "stars": "⭐" * stars,
                "m_h": get_momentum_weight(t_h['recent_form']),
                "m_a": get_momentum_weight(t_a['recent_form'])
            })

    if not results: return

    final_list = sorted(results, key=lambda x: x['prob'], reverse=True)
    
    msg = "🏆 *137BET V17.2 - QUANTUM PARISI*\n"
    msg += "📡 _Filtro Pauli + Indice Parisi (PP)_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for b in final_list:
        h_boost = "📈" if b['m_h'] > 1.05 else "📉" if b['m_h'] < 0.95 else "➖"
        a_boost = "📈" if b['m_a'] > 1.05 else "📉" if b['m_a'] < 0.95 else "➖"
        
        msg += (f"🕒 {b['time']} - {b['match']}\n"
                f"🔥 Fiducia: {b['stars']}\n"
                f"📊 Form: {h_boost} vs {a_boost}\n"
                f"🛡️ Filtro Pauli: *{b['advice']}*\n"
                f"🌀 PP Index: `{b['pp_diff']}`\n"
                f"💡 **SENTENZA PP: {b['pp_sentenza']}**\n"
                f"🎯 Segno STD: *{b['segno']}* ({round(b['prob']*100)}%)\n"
                f"💠 Pauli P: `{b['pauli_p']}`\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
