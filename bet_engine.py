import os
import numpy as np
import requests
from scipy.stats import poisson
from supabase import create_client
from thefuzz import process
from datetime import datetime, timedelta, timezone

# --- CONFIGURAZIONE ---
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def calculate_ranking_logic(p1, px, p2, delta, sentenza):
    """ V18.6/7 - PURE POISSON SUM """
    probs = {"1": p1, "X": px, "2": p2}
    best_s = max(probs, key=probs.get)
    max_p = probs[best_s]
    if max_p >= 0.60: return round(max_p * 100, 2), best_s
    if best_s == "1": r_sign, base_p = ("1X" if px > p2 else "12"), (p1 + max(px, p2))
    elif best_s == "X": r_sign, base_p = ("1X" if p1 > p2 else "X2"), (px + max(p1, p2))
    else: r_sign, base_p = ("X2" if px > p1 else "12"), (p2 + max(px, p1))
    return round(base_p * 100, 2), r_sign

def get_momentum_weight(form_string):
    if not form_string: return 1.0
    # Portiamo l'analisi della forma a 5 partite se disponibile
    clean_form = form_string.replace(',', '')[-5:]
    points = sum({'W': 3, 'D': 1, 'L': 0}.get(c, 0) for c in clean_form)
    # Raffreddiamo leggermente il peso (divisore 60 invece di 50) per evitare sbalzi eccessivi
    return round(1 + (points - 7.5) / 60, 3)

def get_pp_analysis(t_h, t_a):
    def calculate_intensity(stats, is_home):
        # Utilizziamo i dati p3, g3_f, g3_s che rappresentano l'intensità recente
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

def get_full_analysis_debug(t_h, t_a):
    """ Versione con LOG di Debug per trovare errori nei dati """
    m_h, m_a = get_momentum_weight(t_h['recent_form']), get_momentum_weight(t_a['recent_form'])
    
    # ALERT: Qui usiamo 'avg_scored' (Generale) per casa e 'goals_scored_away' (Specifica) per ospite
    # Verifichiamo se questa asimmetria crea il bug
    lam_h = (t_h['avg_scored'] * t_a['avg_conceded']) * m_h * 1.10 # Ridotto da 1.15
    lam_a = (t_a['goals_scored_away'] * t_h['avg_conceded']) * m_a * 0.95 # Aumentato da 0.90
    
    print(f"\n🔍 AUDIT: {t_h['team_name']} vs {t_a['team_name']}")
    print(f"  - [CASA] Med Scored: {t_h['avg_scored']} | Mom: {m_h} | Lam_H: {round(lam_h, 2)}")
    print(f"  - [AWAY] Med Scored Away: {t_a['goals_scored_away']} | Mom: {m_a} | Lam_A: {round(lam_a, 2)}")
    print(f"  - [DEFENSE] Conceded H: {t_h['avg_conceded']} | Conceded A: {t_a['avg_conceded']}")

    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            probs[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
    
    probs /= probs.sum()
    p1, px, p2 = np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))
    return p1, px, p2, "EQUILIBRIO"

# ... (resto delle funzioni save_prediction_137bet e run_analysis invariate)
