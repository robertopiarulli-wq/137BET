import numpy as np

def find_value(prob_model, odds):

    values = prob_model * np.array(odds)

    idx = np.argmax(values)

    if values[idx] > 1:
        return True, idx, values[idx]

    return False, idx, values[idx]
