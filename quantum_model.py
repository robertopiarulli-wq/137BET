def calculate_quantum_probabilities(match):
    """
    Calcola probabilità quantistiche basate sulle quote
    """
    # Estrazione quote
    odds = match['odds']  # già convertite in lista [home, draw, away]

    # Convertiamo quote in probabilità
    prob_home = 1 / odds[0]
    prob_draw = 1 / odds[1]
    prob_away = 1 / odds[2]

    # Normalizziamo
    total = prob_home + prob_draw + prob_away
    prob_home /= total
    prob_draw /= total
    prob_away /= total

    # Creiamo parametri fittizi per il modello quantistico
    market_move = prob_home - prob_away           # esempio: squilibrio mercato
    draw_factor = prob_draw                        # probabilità pareggio
    strength = (prob_home + prob_away) / 2        # forza combinata squadre

    state = [prob_home, prob_draw, prob_away]

    # Chiama evolve_state con valori derivati
    return evolve_state(state, market_move, draw_factor, strength)
