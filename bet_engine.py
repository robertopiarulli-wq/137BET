import os
import numpy as np
from scipy.stats import poisson
from supabase import create_client
from itertools import combinations

# Setup Supabase
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
ALPHA = 0.0073 # La tua costante di filtraggio

def get_poisson_probs(att_h, def_h, att_a, def_a, avg_h, avg_a):
    lam_h = att_h * def_a * avg_h
    lam_a = att_a * def_h * avg_a
    # Matrice probabilità gol 0-5
    probs = np.array([[poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a) for j in range(6)] for i in range(6)])
    return np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))

def run_analysis():
    # 1. Recupero dati da Supabase
    matches = supabase.table("matches").select("*").eq("status", "scheduled").execute().data
    stats = supabase.table("view_team_stats").select("*").execute().data
    
    picks = []
    for m in matches:
        # Recupero statistiche squadre (qui dovresti mappare le stats ai match)
        # ... logic per estrarre att/def dalle stats ...
        
        p_home, p_draw, p_away = get_poisson_probs(att_h, def_h, att_a, def_a, 1.5, 1.2) # Esempi medie
        
        # 2. Filtraggio con Alfa
        book_p_home = 1 / m['odd_home']
        edge = p_home - book_p_home
        
        if edge > ALPHA:
            picks.append({'match_id': m['id'], 'p_win': p_home, 'league': m['league']})

    # 3. Generazione Combinazioni Coerenti
    combos = [c for c in combinations(picks, 3) if len({p['league'] for p in c}) == 3]
    
    for c in combos:
        prob_tot = np.prod([p['p_win'] for p in c])
        if prob_tot > 0.20:
            supabase.table("final_picks").insert({
                "combo_data": str(c), 
                "prob_tot": float(prob_tot)
            }).execute()

if __name__ == "__main__":
    run_analysis()
