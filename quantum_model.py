# quantum_model.py

def evolve_state(state, market_move, draw_factor, strength):
    alpha = 1 / 137
    new_state = [s*(1+alpha*market_move) for s in state]
    new_state[1] *= (1 + alpha*draw_factor)
    total = sum(new_state)
    return [s/total for s in new_state]

def calculate_quantum_probabilities(match):
    odds = match['odds']
    prob_home = 1 / odds[0]
    prob_draw = 1 / odds[1]
    prob_away = 1 / odds[2]

    total = prob_home + prob_draw + prob_away
    prob_home /= total
    prob_draw /= total
    prob_away /= total

    market_move = prob_home - prob_away
    draw_factor = prob_draw
    strength = (prob_home + prob_away)/2

    state = [prob_home, prob_draw, prob_away]
    return evolve_state(state, market_move, draw_factor, strength)
