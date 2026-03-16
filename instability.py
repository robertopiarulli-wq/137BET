import numpy as np

def calc_instability_score(prob_model, match):
    odds = np.array(match['odds'])
    prob_book = 1/odds
    prob_book /= prob_book.sum()
    delta = np.abs(prob_model - prob_book)
    return 137 * delta
