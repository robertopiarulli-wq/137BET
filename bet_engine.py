import os
import numpy as np
import requests
from scipy.stats import poisson
from supabase import create_client
from itertools import combinations

# Setup Connessioni
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
ALPHA = 0.0073  # La tua costante di filtraggio

def get_poisson_probs(att_h, def_h, att_a, def_a, avg_h, avg_a):
    """Calcola le probabilità 1, X, 2 usando la distribuzione di Poisson."""
    lam_h = att_h * def_a * avg_h
    lam_a = att_a * def_h * avg_a
    # Creazione matrice risultati (0-5 gol)
    probs = np.array([[poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a) for j in range(6)] for i in range(6)])
    
    p_win = np.sum(np.tril(probs, -1)) # Casa
    p_draw = np.sum(np.diag(probs))     # Pareggio
    p_loss = np.sum(np.triu(probs, 1))  # Ospite
    return p_win, p_draw, p_loss

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def run_analysis():
    # 1. Recupero Dati
    matches = supabase.table("matches").select("*").eq("status", "scheduled").execute().data
    stats = supabase.table("view_team_stats").select("*").execute().data
    
    # Mappatura stats per accesso rapido
    stats_map = {s['team_id']: s for s in stats}
    
    picks = []
    for m in matches:
        s_home = stats_map.get(m['home_team_id'])
        s_away = stats_map.get(m['away_team_id'])
        
        if s_home and s_away:
            # Calcolo probabilità con Poisson
            p_home, _, _ = get_poisson_probs(s_home['avg_scored'], s_home['avg_conceded'], 
                                             s_away['avg_scored'], s_away['avg_conceded'], 1.5, 1.2)
            
            # 2. Filtraggio con Alfa
            book_p_home = 1 / m['odd_home']
            edge = p_home - book_p_home
            
            if edge > ALPHA:
                picks.append({'match': f"{m['home_team_id']} vs {m['away_team_id']}", 
                              'p_win': p_home, 'league': m['league']})

    # 3. Generazione Combinazioni Coerenti (Triple)
    combos = [c for c in combinations(picks, 3) if len({p['league'] for p in c}) == 3]
    
    if combos:
        msg = "🚀 *Bet Engine: Analisi Completata*\n\n"
        for i, c in enumerate(combos[:3]): # Invia le migliori 3
            prob_tot = np.prod([p['p_win'] for p in c])
            msg += f"Combo {i+1} (P: {prob_tot:.2%}):\n"
            for item in c: msg += f"- {item['match']} ({item['league']})\n"
            msg += "\n"
        send_telegram_msg(msg)
    else:
        send_telegram_msg("⚠️ Nessuna combinazione soddisfa il filtro Alfa oggi.")

if __name__ == "__main__":
    run_analysis()
