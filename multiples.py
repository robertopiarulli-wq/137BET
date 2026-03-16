import numpy as np
from config import PAULI_CORR_THRESHOLD

def generate_multiple_matrix(probs_list):
    matrix = probs_list[0]
    for p in probs_list[1:]:
        matrix = np.outer(matrix, p)
    return matrix

def apply_pauli_filter(matrix):
    filtered = []
    reshaped = matrix.reshape(-1, matrix.shape[-1]) if len(matrix.shape) > 1 else matrix
    for combo in reshaped:
        corr = np.corrcoef(combo)
        if np.all(corr < PAULI_CORR_THRESHOLD):
            filtered.append(combo)
    return np.array(filtered)
