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

# --- LOGICHE DI PESO V17 ---

def get_momentum_weight(form_string):
    if not form_string: return 1.0
    clean_form = form_string.replace(',', '')[-5:]
    points = sum({'W': 3, 'D': 1, 'L': 0}.get(c, 0) for c in clean_form)
    return round(1 + (points - 7.5) / 50, 3)

def get_defensive_factor(cs_count):
    # Un Clean Sheet riduce la probabilità di subire gol (max 15% di riduzione)
    # Media stimata 10 match: 3 CS è la media. Sopra 3 è un bonus.
    bonus = (cs_count - 3) * 0.02
    return round(1 - max(-0.15, min(0.15, bonus)), 3)

# --- ENGINE DI ANALISI QUANTISTICA V17 ---

def get_pauli_v17(t_h, t_a):
    alpha = 1 / 137.036
    sigma = alpha ** 2
    pauli_threshold = 137 * sigma
    
    m_h, m_a = get_momentum_weight(t_h['recent_form']), get_momentum_weight(t_a['recent_form'])
    
    # Impatto arricchito da Away Power
    impact_h = (t_h['avg_scored'] * t_a['avg_conceded']) * m_h
    impact_a = (t_a['goals_scored_away'] * t_h['avg_conceded']) * m_a # Usa Away Power per l'ospite
    
    pauli_p = (impact_h * impact_a) * sigma * 1000
    return round(pauli_p, 6)

def get_full_analysis_v17(t_h, t_a):
    # 1. Calcolo pesi Momentum e Difesa
    m_h, m_a = get_momentum_weight(t_h['recent_form']), get_momentum_weight(t_a['recent_form'])
    def_h, def_a = get_defensive_factor(t_h['clean_sheets']), get_defensive_factor(t_a['clean_sheets'])
    
    # 2. Calcolo Lambda (Gol attesi) con Away Power e Clean Sheet Factor
    # lam_h: Attacco Casa vs Difesa Ospite (corretta da Clean Sheet e Momentum)
    lam_h = (t_h['avg_scored'] * (t_a['avg_conceded'] * def_a)) * m_h * 1.15
    # lam_a: Attacco Fuori (Away Power) vs Difesa Casa (corretta da Clean Sheet e Momentum)
    lam_a = (t_a['goals_scored_away'] * (t_h['avg_conceded'] * def_h)) * m_a * 0.90
    
    # 3. Generazione matrice Poisson
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            probs[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            
    probs /= probs.sum()
    
    p1 = np.sum(np.tril(probs, -1))
    px = np.sum(np.diag(probs))
    p2 = np.sum(np.triu(probs, 1))
    
    return p1, px, p2

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

            p1, px, p2 = get_full_analysis_v17(t_h, t_a)
            pauli_p = get_pauli_v17(t_h, t_a)
            
            # Determinazione segno e fiducia
            outcomes = [('1', p1), ('X', px), ('2', p2)]
            best_s, prob_final = max(outcomes, key=lambda x: x[1])
            
            # Confidence Score (1-5 stelle) basato sulla polarizzazione della probabilità
            stars = min(5, max(1, int(prob_final * 10) - 2)) 
            
            # Salvataggio storico
            try:
                supabase.table("predictions_history").insert({
                    "match_name": f"{m['home_team_name']} vs {m['away_team_name']}",
                    "match_date": m['match_date'],
                    "predicted_sign": best_s,
                    "probability": round(float(prob_final), 4),
                    "pauli_p": float(pauli_p)
                }).execute()
            except: pass
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "time": format_date(m['match_date']),
                "segno": best_s, 
                "prob": prob_final,
                "pauli_p": pauli_p,
                "stars": "⭐" * stars,
                "m_h": get_momentum_weight(t_h['recent_form']),
                "m_a": get_momentum_weight(t_a['recent_form'])
            })

    if not results: return

    final_list = sorted(results, key=lambda x: x['prob'], reverse=True)
    
    msg = "🏆 *137BET V17.0 - TOTAL GRAVITY*\n"
    msg += "📡 _Weighted: Poisson + Momentum + CS + Away_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for b in final_list:
        h_boost = "📈" if b['m_h'] > 1.05 else "📉" if b['m_h'] < 0.95 else "➖"
        a_boost = "📈" if b['m_a'] > 1.05 else "📉" if b['m_a'] < 0.95 else "➖"
        
        msg += (f"🕒 {b['time']} - {b['match']}\n"
                f"🔥 Fiducia: {b['stars']}\n"
                f"📊 Form: {h_boost} vs {a_boost}\n"
                f"🎯 Segno: *{b['segno']}* ({round(b['prob']*100)}%)\n"
                f"💠 Pauli P: `{b['pauli_p']}`\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
