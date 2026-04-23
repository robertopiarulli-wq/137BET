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
    V18.9 Platinum - COORDINAMENTO FISICA STATISTICA
    Applica la Tabella Decisionale simmetrica e il Rank Score Poisson.
    """
    probs = {"1": p1, "X": px, "2": p2}
    sent = sentenza.upper()
    
    # 1. FILTRO ANTI-TOPPA (Se Poisson >= 60%, domina la direzione)
    if p1 >= 0.60: return round((p1 + px) * 100, 2), "1X"
    if p2 >= 0.60: return round((px + p2) * 100, 2), "X2"

    # 2. LOGICA COORDINATA (FISSA X / 12 / DOPPIE)
    if "FISSA X" in sent:
        # X + max(1,2)
        r_sign = "X2" if p2 > p1 else "1X"
        base_p = px + max(p1, p2)
    elif "12" in sent or "1-2" in sent:
        # 1 + 2
        r_sign = "12"
        base_p = p1 + p2
    elif "1X" in sent:
        # 1 + X
        r_sign = "1X"
        base_p = p1 + px
    elif "X2" in sent:
        # X + 2
        r_sign = "X2"
        base_p = px + p2
    elif "FISSA 1" in sent:
        r_sign = "1"
        base_p = p1
    elif "FISSA 2" in sent:
        r_sign = "2"
        base_p = p2
    else:
        # Fallback
        r_sign = max(probs, key=probs.get)
        base_p = probs[r_sign]

    return round(base_p * 100, 2), r_sign

def get_pp_analysis(t_h, t_a):
    """
    IMPLEMENTAZIONE KPZ / PARISI
    """
    def calculate_kpz_intensity(stats, is_home):
        # Formula I: Punti*0.6 + (GF*peso) - (GS*peso)
        points = sum({'W': 3, 'D': 1, 'L': 0}.get(c, 0) for c in stats.get('recent_form', '').replace(',', '')[-5:])
        if is_home:
            return (points * 0.6) + (stats.get('avg_scored', 0) * 0.30) - (stats.get('avg_conceded', 0) * 0.15)
        else:
            return (points * 0.6) + (stats.get('avg_scored', 0) * 0.36) - (stats.get('avg_conceded', 0) * 0.10)
    
    ih = calculate_kpz_intensity(t_h, True)
    ia = calculate_kpz_intensity(t_a, False)

    # Distanza Lineare D (Metodo Parisi Segni Concordi/Discordi)
    if (ih >= 0 and ia >= 0) or (ih < 0 and ia < 0):
        delta = ih - ia
    else:
        # Discordi: |Ih| + |Ia| con segno del positivo
        delta = (abs(ih) + abs(ia)) * (1 if ih > ia else -1)
    
    delta = round(delta, 2)
    abs_d = abs(delta)

    # Tabella Decisionale Simmetrica
    if abs_d > 8:
        sentenza = "🎯 FISSA 1" if ih > ia else "🎯 FISSA 2"
    elif 4 < abs_d <= 8:
        sentenza = "🔀 DOPPIA 12"
    elif 2 < abs_d <= 4:
        sentenza = "🛡️ DOPPIA 1X" if ih > ia else "🛡️ DOPPIA X2"
    else:
        sentenza = "🔒 FISSA X"

    return delta, sentenza

def run_analysis():
    print("🚀 Avvio 137BET V18.9 Platinum - The Vault...")
    matches = supabase.table("matches").select("*").execute().data
    teams_data = supabase.table("teams").select("*").execute().data
    stats_map = {t['team_name']: t for t in teams_data}
    
    results = []
    for m in matches:
        try:
            h_res = process.extractOne(m['home_team_name'], list(stats_map.keys()), score_cutoff=35)
            a_res = process.extractOne(m['away_team_name'], list(stats_map.keys()), score_cutoff=35)
            
            if h_res and a_res:
                t_h, t_a = stats_map[h_res[0]], stats_map[a_res[0]]
                
                # Poisson (Avg Scored/Conceded)
                lam_h = (t_h['avg_scored'] * t_a['avg_conceded']) * 1.10
                lam_a = (t_a['avg_scored'] * t_h['avg_conceded'])
                probs = np.zeros((6, 6))
                for i in range(6):
                    for j in range(6):
                        probs[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
                probs /= probs.sum()
                p1, px, p2 = np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

                # Analisi KPZ/Parisi
                delta, sentenza = get_pp_analysis(t_h, t_a)
                rank_p, rank_s = calculate_ranking_logic(p1, px, p2, delta, sentenza)

                results.append({
                    "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                    "date": m['match_date'].split('T')[0],
                    "p1": p1, "px": px, "p2": p2,
                    "delta": delta, "sentenza": sentenza,
                    "rank": rank_p, "segno": rank_s
                })
        except Exception as e: print(f"⚠️ Errore: {e}")

    if results:
        # ORDINAMENTO DECRESCENTE RANK
        final_list = sorted(results, key=lambda x: x['rank'], reverse=True)
        
        for i in range(0, len(final_list), 5):
            msg = "🏆 *137BET V18.9 PLATINUM*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            for b in final_list[i:i+5]:
                msg += (f"📅 {b['date']} | {b['match']}\n"
                        f"📊 Poisson: `{round(b['p1']*100)}%|{round(b['px']*100)}%|{round(b['p2']*100)}%`\n"
                        f"📏 **Rank: {b['rank']}%** | D: {b['delta']}\n"
                        f"💡 PP: {b['sentenza']} -> **{b['segno']}**\n"
                        f"────────────────\n")
            send_telegram_msg(msg)

if __name__ == "__main__":
    run_analysis()
