import numpy as np
from config import ALPHA

F = np.array([[1,0,0],[0,0,0],[0,0,-1]])
D = np.array([[0,0,0],[0,1,0],[0,0,0]])
M = np.array([[0,1,0],[1,0,1],[0,1,0]])

def quantum_state(p1, px, p2):
    return np.array([np.sqrt(p1), np.sqrt(px), np.sqrt(p2)])

def evolve_state(state, w1, w2, w3):
    H = w1*F + w2*D + w3*M
    new_state = state + ALPHA * H.dot(state)
    new_state /= np.linalg.norm(new_state)
    return np.abs(new_state)**2

def calculate_quantum_probabilities(match):
    odds = match['odds']
    prob_book = np.array(odds)**-1
    prob_book /= prob_book.sum()
    state = quantum_state(prob_book[0], prob_book[1], prob_book[2])
    return evolve_state(state, match['market_move'], match['draw_factor'], match['strength'])
