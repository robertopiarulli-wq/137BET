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
    V18.9 PLATINUM - COORDINAMENTO PURO (No Peso D)
    Il Rank è la SOMMA PURA delle probabilità Poisson coordinata con Parisi.
    """
    if "X" in sentenza:
        # Se la PP impone la X, la doppia è X + il miglior Poisson tra 1 e 2
        if p2 > p1:
            r_sign, base_p = "X2", (px + p2)
        else:
            r_sign, base_p = "1X", (px + p1)
    elif "12" in sentenza:
        r_sign, base_p = "12", (p1 + p2)
    elif "1" in sentenza and "FISSA" in sentenza:
        r_sign, base_p = "1", p1
    elif "2" in sentenza and "FISSA" in sentenza:
        r_sign, base_p = "2", p2
    else:
        # Fallback: Segno dominante Poisson
        probs = {"1": p1, "X": px, "2": p2}
        r_sign = max(probs, key=probs.get)
        base_p = probs[r_sign]

    return round(base_p * 100, 2), r_sign

def save_prediction_137bet(data):
    """ Salva ogni run con timestamp per Backtest storico senza duplicati nel report """
    try:
        supabase.table("prediction_history_137bet").insert({
            "match_name": data['match'], 
            "match_date": data['time'],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pp_diff": data['pp_diff'], 
            "pp_sentenza": data['pp_sentenza'],
            "prob_1": round(data['p1'], 4), 
            "prob_x": round(data['px'], 4), 
            "prob_2": round(data['p2'], 4),
            "ranking_power": data['rank_p'],  
            "ranking_sign": data['segno']    
        }).execute()
    except Exception as e: 
        print(f"⚠️ Errore DB: {e}")

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

def run_analysis():
    print("🚀 Esecuzione 137BET V18.9 Platinum...")
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    stats_map = {t['team_name']: t for t in teams_data}
    team_list = list(stats_map.keys())

    results = []
    now = datetime.now(timezone.utc)

    for m in matches:
        try:
            h_res = process.extractOne(m['home_team_name'], team_list, score_cutoff=40)
            a_res = process.extractOne(m['away_team_name'], team_list, score_cutoff=40)

            if h_res and a_res:
                t_h, t_a = stats_map[h_res[0]], stats_map[a_res[0]]
                
                # Poisson V18.9 - Medie Omogenee (Fix Barcellona)
                m_h, m_a = get_momentum_weight(t_h['recent_form']), get_momentum_weight(t_a['recent_form'])
                lam_h = (t_h['avg_scored'] * t_a['avg_conceded']) * m_h * 1.10
                lam_a = (t_a['avg_scored'] * t_h['avg_conceded']) * m_a
                if t_a['avg_conceded'] < 1.05: lam_a = max(lam_a, 1.15)

                probs = np.zeros((6, 6))
                for i in range(6):
                    for j in range(6):
                        probs[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
                probs /= probs.sum()
                p1, px, p2 = np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

                delta, sent = get_pp_analysis(t_h, t_a)
                rank_val, rank_sign = calculate_ranking_logic(p1, px, p2, delta, sent)

                res = {
                    "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                    "time": m['match_date'], "p1": p1, "px": px, "p2": p2,
                    "pp_diff": delta, "pp_sentenza": sent, "rank_p": rank_val, "segno": rank_sign,
                    "stars": "⭐" * min(5, max(1, int(max(p1, px, p2) * 10) - 2)),
                    "m_h": m_h, "m_a": m_a
                }
                save_prediction_137bet(res)
                results.append(res)
        except Exception as e: print(f"⚠️ Errore match: {e}")

    if results:
        # ORDINAMENTO DECISIVO PER RANK POWER
        final_list = sorted(results, key=lambda x: x['rank_p'], reverse=True)
        header = "🏆 *137BET V18.9 - PLATINUM*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i in range(0, len(final_list), 5):
            chunk = final_list[i:i + 5]
            msg = header + f"📦 *TOP RANKING ({i//5 + 1})*\n\n"
            for b in chunk:
                msg += (f"🕒 {b['match']}\n"
                        f"📏 **Rank: {b['rank_p']}%** | {b['stars']}\n"
                        f"💡 SENTENZA PP: `{b['pp_sentenza']}`\n"
                        f"📊 DASHBOARD: *{b['segno']}*\n"
                        f"────────────────\n")
            send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
