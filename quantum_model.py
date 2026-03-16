# quantum_model.py

def evolve_state(state, market_move, draw_factor, strength):
    """
    Evoluzione quantistica semplificata:
    modifica leggermente le probabilità in base ai parametri
    """
    alpha = 1 / 137  # costante quantistica

    # oscillazioni leggere sulle probabilità
    new_state = [
        s * (1 + alpha * market_move) for s in state
    ]

    # aggiustamento probabilità pareggio
    new_state[1] *= (1 + alpha * draw_factor)

    # normalizzazione totale
    total = sum(new_state)
    new_state = [s/total for s in new_state]

    return new_state


def calculate_quantum_probabilities(match):
    """
    Calcola probabilità quantistiche basate sulle quote
    """
    odds = match['odds']  # lista [home, draw, away]

    # Convertiamo quote in probabilità
    prob_home = 1 / odds[0]
    prob_draw = 1 / odds[1]
    prob_away = 1 / odds[2]

    # Normalizziamo
    total = prob_home + prob_draw + prob_away
    prob_home /= total
    prob_draw /= total
    prob_away /= total

    # Parametri per evolve_state
    market_move = prob_home - prob_away
    draw_factor = prob_draw
    strength = (prob_home + prob_away) / 2

    state = [prob_home, prob_draw, prob_away]

    # chiama la funzione evolve_state definita sopra
    return evolve_state(state, market_move, draw_factor, strength)
