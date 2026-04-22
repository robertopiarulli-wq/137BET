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
    V18.8 - PURE POISSON SUM (Anti-Paradox)
    """
    probs = {"1": p1, "X": px, "2": p2}
    best_s = max(probs, key=probs.get)
    max_p = probs[best_s]

    if max_p >= 0.60:
        return round(max_p * 100, 2), best_s

    if best_s == "1":
        r_sign, base_p = ("1X" if px > p2 else "12"), (p1 + max(px, p2))
    elif best_s == "X":
        r_sign, base_p = ("1X" if p1 > p2 else "X2"), (px + max(p1, p2))
    else:
        r_sign, base_p = ("X2" if px > p1 else "12"), (p2 + max(px, p1))

    return round(base_p * 100, 2), r_sign

def save_prediction_137bet(data):
    try:
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
    # Analisi della forma su 5 partite
    clean_form = form_string.replace(',', '')[-5:]
    points = sum({'W': 3, 'D': 1, 'L': 0}.get(c, 0) for c in clean_form)
    # Divisore a 60 per raffreddare l'impatto del momento recente
    return round(1 + (points - 7.5) / 60, 3)

def get_pp_analysis(t_h, t_a):
    def calculate_intensity(stats, is_home):
        # Utilizziamo p3, g3_f, g3_s per l'intensità Parisi
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

def get_full_analysis_v18_8(t_h, t_a):
    """ Versione Anti-Paradosso con Logica Omogenea e Salvaguardia Top Team """
    m_h = get_momentum_weight(t_h['recent_form'])
    m_a = get_momentum_weight(t_a['recent_form'])
    
    # Calcolo Lambda base usando Medie Omogenee (avg_scored per entrambe)
    base_lam_h = t_h['avg_scored'] * t_a['avg_conceded']
    base_lam_a = t_a['avg_scored'] * t_h['avg_conceded']

    # Applicazione Momentum e Fattore Campo (1.10 Casa, 1.00 Ospite)
    lam_h = base_lam_h * m_h * 1.10
    lam_a = base_lam_a * m_a * 1.00
    
    # Clausola di Salvaguardia: Se l'ospite è un Top Team (difesa solida < 1.0)
    # non permettiamo che i gol attesi crollino sotto una soglia di dignità tecnica.
    if t_a['avg_conceded'] < 1.05:
        lam_a = max(lam_a, 1.15)

    print(f"🔍 AUDIT FIX V18.8: {t_h['team_name']} vs {t_a['team_name']}")
    print(f"   [CASA] Media:{t_h['avg_scored']} Mom:{m_h} -> LamH:{round(lam_h,2)}")
    print(f"   [AWAY] Media:{t_a['avg_scored']} Mom:{m_a} -> LamA:{round(lam_a,2)}")

    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            probs[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
    
    probs /= probs.sum()
    p1 = np.sum(np.tril(probs, -1))
    px = np.sum(np.diag(probs))
    p2 = np.sum(np.triu(probs, 1))
    
    return p1, px, p2, "EQUILIBRIO"

def run_analysis():
    print("🚀 Avvio 137BET V18.8 - Anti-Paradox Edition...")
    
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
                
                # Chiamata alla nuova analisi V18.8
                p1, px, p2, advice = get_full_analysis_v18_8(t_h, t_a)
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
        header = "🏆 *137BET V18.8 - ANTI-PARADOX*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i in range(0, len(final_list), 5):
            chunk = final_list[i:i + 5]
            msg = header + f"📦 *SENTENZE DEL WEEKEND ({(i//5) + 1})*\n\n"
            for b in chunk:
                r_pow, r_sign = calculate_ranking_logic(b['p1'], b['px'], b['p2'], b['pp_diff'], b['pp_sentenza'])
                
                h_b = "📈" if b['m_h'] > 1.05 else "📉" if b['m_h'] < 0.95 else "➖"
                a_b = "📈" if b['m_a'] > 1.05 else "📉" if b['m_a'] < 0.95 else "➖"
                msg += (f"🕒 {b['time']} - {b['match']}\n"
                        f"🔥 Fiducia: {b['stars']} | Form: {h_b} vs {a_b}\n"
                        f"📏 Delta PP: `{b['pp_diff']}` | **Rank: {r_pow}%**\n"
                        f"💡 **SENTENZA: {b['pp_sentenza']}**\n"
                        f"📊 In Dashboard: *{r_sign}*\n"
                        f"────────────────\n")
            
            send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
