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
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                          data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
                          timeout=15)
        except Exception as e:
            print(f"⚠️ Errore invio Telegram: {e}")

def calculate_optimized_ranking(p1, px, p2, delta, sentenza):
    """
    RANKING OTTIMIZZATO V18.3 - QUANTUM COHERENCE
    Bilancia Probabilità Poisson (Statistica) e Delta Parisi (Tattica)
    """
    # 1. Normalizzazione Forza del Delta (scala 0-1 basata su 15 come max)
    delta_power = min(abs(delta) / 15, 1.0)
    
    probs = {"1": p1, "X": px, "2": p2}
    best_s = max(probs, key=probs.get)
    max_p = probs[best_s]

    # --- CASO A: FISSA STATISTICA (>= 60%) ---
    if max_p >= 0.60:
        # Bonus coerenza se la direzione PP conferma la probabilità Poisson
        bonus_coerenza = 0.05 if (delta > 4 and best_s == "1") or (delta < -4 and best_s == "2") else 0
        # Formula pesata: 75% Statistica, 20% Forza Delta, 5% Coerenza
        ranking_val = (max_p * 0.75) + (delta_power * 0.20) + bonus_coerenza
        return round(min(ranking_val, 1.0) * 100, 2), best_s

    # --- CASO B: DOPPIA DINAMICA (Sotto il 60%) ---
    # Logica base G: PP + miglior segno restante
    if "12" in sentenza:
        base_prob = p1 + p2
        r_sign = "12"
    elif "X" in sentenza:
        base_prob = px + max(p1, p2)
        r_sign = "1X" if p1 > p2 else "X2"
    elif "1" in sentenza:
        base_prob = p1 + max(px, p2)
        r_sign = "1X" if px > p2 else "12"
    elif "2" in sentenza:
        base_prob = p2 + max(p1, px)
        r_sign = "X2" if px > p1 else "12"
    else:
        base_prob = max_p
        r_sign = best_s

    # Il ranking per le doppie viene validato per l'80% dalla probabilità 
    # e per il 20% dalla grandezza del Delta Parisi
    ranking_val = (base_prob * 0.80) + (delta_power * 0.20)
    
    return round(min(ranking_val, 1.0) * 100, 2), r_sign

def save_prediction_137bet(data):
    try:
        # Calcolo del Ranking Ottimizzato V18.3
        rank_p, rank_s = calculate_optimized_ranking(
            data['p1'], data['px'], data['p2'], data['pp_diff'], data['pp_sentenza']
        )
        
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
            "away_momentum": data['m_a'],
            "ranking_power": rank_p,  
            "ranking_sign": rank_s    
        }).execute()
    except Exception as e: 
        print(f"⚠️ Errore DB: {e}")

def format_date(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00').replace(' ', 'T'))
        return dt.strftime("%d/%m %H:%M")
    except: return "N.D."

def get_momentum_weight(form_string):
    if not form_string: return 1.0
    clean_form = form_string.replace(',', '')[-5:]
    points = sum({'W': 3, 'D': 1, 'L': 0}.get(c, 0) for c in clean_form)
    return round(1 + (points - 7.5) / 50, 3)

def get_defensive_factor(cs_count):
    bonus = (cs_count - 3) * 0.02
    return round(1 - max(-0.15, min(0.15, bonus)), 3)

def get_pp_analysis(t_h, t_a):
    def calculate_intensity(stats, is_home):
        p3, g3_f, g3_s = stats.get('p3', 0), stats.get('g3_f', 0), stats.get('g3_s', 0)
        sigma = stats.get('s3', 1.0)
        return (p3 + (g3_f * 0.5) - (g3_s * (0.8 if is_home else 0.5))) / (1 + sigma)
    
    i_h = calculate_intensity(t_h, True)
    i_a = calculate_intensity(t_a, False)
    delta = round(i_h - i_a, 2)

    # Logica Distanza Lineare Pura G
    if delta > 8: sentenza = "🎯 FISSA 1"
    elif delta < -8: sentenza = "🎯 FISSA 2"
    elif 4 < delta <= 8 or -8 <= delta < -4: sentenza = "🔀 DOPPIA 12"
    elif 2 < delta <= 4: sentenza = "🛡️ DOPPIA 1X"
    elif -4 <= delta < -2: sentenza = "🛡️ DOPPIA X2"
    elif -2 <= delta <= 2: sentenza = "🔒 FISSA X"
    else: sentenza = "🔀 DOPPIA 12"

    return delta, sentenza

def get_full_analysis_v17(t_h, t_a):
    m_h, m_a = get_momentum_weight(t_h['recent_form']), get_momentum_weight(t_a['recent_form'])
    def_h, def_a = get_defensive_factor(t_h['clean_sheets']), get_defensive_factor(t_a['clean_sheets'])
    sigma_q = (1 / 137.036) ** 2
    impact_h = (t_h['avg_scored'] * t_a['avg_conceded']) * m_h
    impact_a = (t_a['goals_scored_away'] * t_h['avg_conceded']) * m_a
    pauli_p = (impact_h * impact_a) * sigma_q * 1000
    exclusion, advice = None, "EQUILIBRIO"
    if pauli_p > 0.18:
        advice, exclusion = "ECCITATO (ESCLUSIONE)", ("2" if impact_h > impact_a else "1")
    elif pauli_p < 0.05: advice = "RISONANZA (X ALTA)"
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
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1)), pauli_p, advice

def run_analysis():
    print("🚀 Avvio 137BET V18.3 - Quantum Ranking Edition...")
    
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    
    stats_map = {t['team_name']: t for t in teams_data}
    team_names_list = list(stats_map.keys())

    now = datetime.now(timezone.utc)
    start_target = now - timedelta(hours=24)
    end_target = now + timedelta(hours=160)
    
    results = []

    for m in matches:
        try:
            m_date_str = m['match_date'].replace('Z', '+00:00').replace(' ', 'T')
            match_time = datetime.fromisoformat(m_date_str)
            
            if not (start_target <= match_time <= end_target):
                continue

            h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=35)
            a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=35)

            if h_res and a_res:
                t_h, t_a = stats_map[h_res[0]], stats_map[a_res[0]]
                p1, px, p2, pauli_p, advice = get_full_analysis_v17(t_h, t_a)
                pp_diff, pp_sentenza = get_pp_analysis(t_h, t_a)
                
                best_s, prob_f = max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])
                
                res = {
                    "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                    "time": format_date(m['match_date']),
                    "segno": best_s, "p1": p1, "px": px, "p2": p2,
                    "advice": advice, "pp_diff": pp_diff, "pp_sentenza": pp_sentenza,
                    "stars": "⭐" * min(5, max(1, int(prob_f * 10) - 2)),
                    "m_h": get_momentum_weight(t_h['recent_form']),
                    "m_a": get_momentum_weight(t_a['recent_form'])
                }
                save_prediction_137bet(res)
                results.append(res)
        except Exception as e:
            print(f"⚠️ Errore nel match {m.get('home_team_name')}: {e}")

    if results:
        final_list = sorted(results, key=lambda x: len(x['stars']), reverse=True)
        header = "🏆 *137BET V18.3 - QUANTUM RANKING*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i in range(0, len(final_list), 5):
            chunk = final_list[i:i + 5]
            msg = header + f"📦 *SENTENZE DEL WEEKEND ({(i//5) + 1})*\n\n"
            for b in chunk:
                # Calcolo ranking al volo per il display Telegram
                r_pow, r_sign = calculate_optimized_ranking(b['p1'], b['px'], b['p2'], b['pp_diff'], b['pp_sentenza'])
                
                h_b = "📈" if b['m_h'] > 1.05 else "📉" if b['m_h'] < 0.95 else "➖"
                a_b = "📈" if b['m_a'] > 1.05 else "📉" if b['m_a'] < 0.95 else "➖"
                msg += (f"🕒 {b['time']} - {b['match']}\n"
                        f"🔥 Fiducia: {b['stars']} | Form: {h_b} vs {a_b}\n"
                        f"📏 Delta PP: `{b['pp_diff']}` | **Rank: {r_pow}%**\n"
                        f"💡 **SENTENZA: {b['pp_sentenza']}**\n"
                        f"📊 In Dashboard: *{r_sign}*\n"
                        f"────────────────\n")
            
            send_telegram_msg(msg)
    else:
        print("❌ Nessun match trovato.")

if __name__ == "__main__":
    run_analysis()
