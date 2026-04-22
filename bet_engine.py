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

def calculate_ranking_logic(p1, px, p2, delta, sentenza):
    """
    V18.9 - COORDINAMENTO PP/POISSON + QUANTUM RANK
    Forza il segno in base alla Sentenza PP e calcola il Rank pesato.
    """
    probs = {"1": p1, "X": px, "2": p2}
    
    # 1. COORDINAMENTO SEGNO (La regola di G)
    if "X" in sentenza:
        # Se la PP impone la X, la doppia deve essere X + il miglior Poisson tra 1 e 2
        if p2 > p1:
            r_sign = "X2"
            base_p = px + p2
        else:
            r_sign = "1X"
            base_p = px + p1
    elif "12" in sentenza:
        r_sign = "12"
        base_p = p1 + p2
    elif "1" in sentenza and "FISSA" in sentenza:
        r_sign = "1"
        base_p = p1
    elif "2" in sentenza and "FISSA" in sentenza:
        r_sign = "2"
        base_p = p2
    else:
        # Fallback su Poisson puro se non ci sono match nelle sentenze
        best_s = max(probs, key=probs.get)
        r_sign = best_s
        base_p = probs[best_s]

    # 2. CALCOLO RANK (85% Probabilità Segno + 15% Forza Delta Parisi)
    delta_power = min(abs(delta) / 15, 1.0)
    ranking_val = (base_p * 0.85) + (delta_power * 0.15)
    
    return round(ranking_val * 100, 2), r_sign

def save_prediction_137bet(data):
    try:
        # Il Rank viene salvato nel DB usando la nuova logica V18.9
        rank_p, rank_s = calculate_ranking_logic(
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
    return round(1 + (points - 7.5) / 60, 3)

def get_pp_analysis(t_h, t_a):
    def calculate_intensity(stats, is_home):
        p3, g3_f, g3_s = stats.get('p3', 0), stats.get('g3_f', 0), stats.get('g3_s', 0)
        sigma = stats.get('s3', 1.0)
        return (p3 + (g3_f * 0.5) - (g3_s * (0.8 if is_home else 0.5))) / (1 + sigma)
    
    i_h = calculate_intensity(t_h, True)
    i_a = calculate_intensity(t_a, False)
    delta = round(i_h - i_a, 2)

    if delta > 8: sentenza = "🎯 FISSA 1"
    elif delta < -8: sentenza = "🎯 FISSA 2"
    elif 4 < delta <= 8 or -8 <= delta < -4: sentenza = "🔀 DOPPIA 12"
    elif 2 < delta <= 4: sentenza = "🛡️ DOPPIA 1X"
    elif -4 <= delta < -2: sentenza = "🛡️ DOPPIA X2"
    else: sentenza = "🔒 FISSA X"

    return delta, sentenza

def get_full_analysis_v18_9(t_h, t_a):
    """ Versione Anti-Paradosso con Medie Omogenee (Bug Barcellona Fix) """
    m_h, m_a = get_momentum_weight(t_h['recent_form']), get_momentum_weight(t_a['recent_form'])
    
    # Usiamo avg_scored per entrambi per stabilità
    base_lam_h = t_h['avg_scored'] * t_a['avg_conceded']
    base_lam_a = t_a['avg_scored'] * t_h['avg_conceded']

    lam_h = base_lam_h * m_h * 1.10
    lam_a = base_lam_a * m_a
    
    # Protezione Top Team
    if t_a['avg_conceded'] < 1.05:
        lam_a = max(lam_a, 1.15)

    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            probs[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
    
    probs /= probs.sum()
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1)), "EQUILIBRIO"

def run_analysis():
    print("🚀 Avvio 137BET V18.9 - The Coordinator Edition...")
    
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
            
            if not (start_target <= match_time <= end_target): continue

            h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=35)
            a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=35)

            if h_res and a_res:
                t_h, t_a = stats_map[h_res[0]], stats_map[a_res[0]]
                p1, px, p2, advice = get_full_analysis_v18_9(t_h, t_a)
                pp_diff, pp_sentenza = get_pp_analysis(t_h, t_a)
                
                # Calcoliamo subito Rank e Segno per l'ordinamento
                r_pow, r_sign = calculate_ranking_logic(p1, px, p2, pp_diff, pp_sentenza)
                
                res = {
                    "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                    "time": format_date(m['match_date']),
                    "segno": r_sign, "p1": p1, "px": px, "p2": p2,
                    "advice": advice, "pp_diff": pp_diff, "pp_sentenza": pp_sentenza,
                    "stars": "⭐" * min(5, max(1, int(max(p1, px, p2) * 10) - 2)),
                    "m_h": get_momentum_weight(t_h['recent_form']),
                    "m_a": get_momentum_weight(t_a['recent_form']),
                    "rank_p": r_pow
                }
                save_prediction_137bet(res)
                results.append(res)
        except Exception as e:
            print(f"⚠️ Errore: {e}")

    if results:
        # ORDINAMENTO DECISIVO PER RANK POWER
        final_list = sorted(results, key=lambda x: x['rank_p'], reverse=True)
        header = "🏆 *137BET V18.9 - COORDINATOR*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i in range(0, len(final_list), 5):
            chunk = final_list[i:i + 5]
            msg = header + f"📦 *SENTENZE TOP RANK ({(i//5) + 1})*\n\n"
            for b in chunk:
                h_b = "📈" if b['m_h'] > 1.05 else "📉" if b['m_h'] < 0.95 else "➖"
                a_b = "📈" if b['m_a'] > 1.05 else "📉" if b['m_a'] < 0.95 else "➖"
                msg += (f"🕒 {b['time']} - {b['match']}\n"
                        f"🔥 Fiducia: {b['stars']} | Form: {h_b} vs {a_b}\n"
                        f"📏 Delta PP: `{b['pp_diff']}` | **Rank: {b['rank_p']}%**\n"
                        f"💡 **SENTENZA: {b['pp_sentenza']}**\n"
                        f"📊 In Dashboard: *{b['segno']}*\n"
                        f"────────────────\n")
            send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
