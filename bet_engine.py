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
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime("%d/%m %H:%M")
    except: return "N.D."

# --- LOGICA MATEMATICA ---
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

def get_full_analysis(team_h, team_a):
    f_h = get_form_multiplier(team_h.get('recent_form'))
    f_a = get_form_multiplier(team_a.get('recent_form'))
    
    avg_goals = 1.25 
    lam_h = (team_h['avg_scored'] * f_h) * (team_a['avg_conceded'] / f_a) * 1.12 * avg_goals
    lam_a = (team_a['avg_scored'] * f_a) * (team_h['avg_conceded'] / f_h) * 0.92 * avg_goals
    
    total_xg = lam_h + lam_a
    
    # MATRICE PROBABILITÀ
    rho = -0.20 
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p_base = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            probs[i,j] = p_base * dixon_coles_tau(i, j, lam_h, lam_a, rho)
    
    probs /= probs.sum()
    p1, px, p2 = np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))
    
    # LOGICA RICHIESTA: U/O basato su xG totali
    combo = "U 3.5" if total_xg < 2.5 else "O 1.5"
    c_prob = sum(probs[i,j] for i in range(6) for j in range(6) if (i+j <= 3 if combo == "U 3.5" else i+j >= 2))
    
    # LOGICA BTTS: xG Casa e Fuori > 1.15
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
    
    print(f"🧐 Database: {len(matches)} match totali.")
    
    for m in matches:
        # Pulizia data per confronto
        m_date_str = m['match_date'].replace(' ', 'T').replace('Z', '') + '+00:00'
        match_time = datetime.fromisoformat(m_date_str)
        
        if match_time < now or match_time > limit_date:
            continue

        h_res = process.extractOne(m['home_team_name'], team_names_list, score_cutoff=60)
        a_res = process.extractOne(m['away_team_name'], team_names_list, score_cutoff=60)

        if h_res and a_res:
            p1, px, p2, combo, c_prob, btts, b_prob = get_full_analysis(stats_map[h_res[0]], stats_map[a_res[0]])
            best_s = 'X' if px >= 0.27 else max([('1', p1), ('X', px), ('2', p2)], key=lambda x: x[1])[0]
            
            results.append({
                "match": f"{m['home_team_name']} vs {m['away_team_name']}",
                "date": m['match_date'], "segno": best_s, 
                "prob": px if best_s == 'X' else max(p1, p2),
                "quota": m.get(f'odds_{best_s.lower()}', 1.0),
                "combo": combo, "c_prob": c_prob,
                "btts": btts, "b_prob": b_prob
            })
        else:
            print(f"⚠️ Nomi non trovati: {m['home_team_name']} o {m['away_team_name']}")

    if not results:
        print("❌ Nessun match ha superato i filtri data/nomi.")
        return

    # SMISTAMENTO 10-4-4
    f_12 = sorted([r for r in results if r['segno'] in ['1', '2']], key=lambda x: x['prob'], reverse=True)[:10]
    f_x = sorted([r for r in results if r['segno'] == 'X'], key=lambda x: x['prob'], reverse=True)[:4]
    
    final_list = f_12 + f_x
    if not final_list: return

    # --- COSTRUZIONE MESSAGGIO ---
    msg = "🚀 *137BET - POWER REPORT xG*\n"
    msg += f"📊 Match analizzati: {len(results)}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    for b in final_list:
        msg += (f"📅 {format_date(b['date'])}\n"
                f"🏟 {b['match']}\n"
                f"🎯 Fissa: *{b['segno']}* ({round(b['prob']*100)}%)\n"
                f"🛡 Combo: *{b['combo']}* ({round(b['c_prob']*100)}%)\n"
                f"💎 BTTS: *{b['btts']}* ({round(b['b_prob']*100)}%)\n"
                f"────────────────\n")
    
    send_telegram_msg(msg)
    print(f"✅ Analisi completata. Inviati {len(final_list)} match.")

if __name__ == "__main__":
    run_analysis()
