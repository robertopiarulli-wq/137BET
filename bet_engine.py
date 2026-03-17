def get_form_multiplier(form_string):
    """
    Trasforma la stringa della forma in un moltiplicatore di forza.
    W=3 punti, D=1 punto, L=0 punti. Media ideale = 7 punti (1.0)
    """
    if not form_string or form_string == 'DDDDD':
        return 1.0
    
    # Pulizia: prendiamo solo gli ultimi 5 caratteri
    form = form_string.replace(',', '')[-5:].upper()
    points = sum(3 if r == 'W' else 1 if r == 'D' else 0 for r in form)
    
    # Regressione lineare semplice: 7 punti = 1.0. 
    # Ogni punto di scarto sposta il valore del 3%
    multiplier = 1.0 + (points - 7) * 0.03
    return max(0.85, min(1.15, multiplier))

def get_full_analysis(team_h, team_a):
    # Recuperiamo la forma dalle colonne di Supabase
    f_h = get_form_multiplier(team_h.get('recent_form', 'DDDDD'))
    f_a = get_form_multiplier(team_a.get('recent_form', 'DDDDD'))
    
    avg_goals = 1.25 
    
    # APPLICAZIONE REGRESSIONE: la forma moltiplica l'attacco e divide la vulnerabilità
    # Se f_h > 1 (forma ottima), lam_h sale. Se f_a < 1 (crisi), lam_h sale ulteriormente.
    lam_h = (team_h['avg_scored'] * f_h) * (team_a['avg_conceded'] / f_a) * 1.12 * avg_goals
    lam_a = (team_a['avg_scored'] * f_a) * (team_h['avg_conceded'] / f_h) * 0.92 * avg_goals
    
    rho = -0.20 # Dixon-Coles
    
    probs = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            p_base = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            probs[i,j] = p_base * dixon_coles_tau(i, j, lam_h, lam_a, rho)
    
    probs /= probs.sum()
    p1, px, p2 = np.sum(np.tril(probs, -1)), np.sum(np.diag(probs)), np.sum(np.triu(probs, 1))
    
    # Combo Larga
    p_u35 = sum(probs[i,j] for i in range(6) for j in range(6) if i+j <= 3)
    p_o15 = 1 - (probs[0,0] + probs[0,1] + probs[1,0])
    
    combo, c_prob = ("U 3.5", p_u35) if p_u35 > 0.60 else ("O 1.5", p_o15)
    return p1, px, p2, combo, c_prob
