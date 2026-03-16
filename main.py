# main.py
from odds_api import get_all_matches
from quantum_model import calculate_quantum_probabilities
from telegram_bot import send_telegram_message
from itertools import combinations

INSTABILITY_THRESHOLD = 0.005  # soglia minima instabilità α

def main():
    print("START BOT")

    matches = get_all_matches()
    print(f"MATCHES FOUND: {len(matches)}")

    value_bets = []
    all_matches = []

    alpha = 1 / 137  # instabilità

    # 1️⃣ Calcolo probabilità quantistiche, EV, instabilità
    for m in matches:
        probs = calculate_quantum_probabilities(m)
        m['quantum_probs'] = probs
        evs = [probs[i] * m['odds'][i] for i in range(3)]
        m['evs'] = evs
        m['expected_value'] = max(evs)
        m['instability'] = abs(probs[0] - probs[2]) * alpha
        all_matches.append(m)

        # Singole Value Bet
        if m['expected_value'] >= 0.99:
            value_bets.append(m)

    print(f"Value bet trovate: {len(value_bets)}")

    # 2️⃣ Filtra partite instabili per combinazioni multiple
    filtered_matches = [m for m in all_matches if m['instability'] > INSTABILITY_THRESHOLD]

    # 3️⃣ Genera combinazioni multiple (top 5)
    top_combinations = []
    for r in [2,3]:  # combinazioni di 2 o 3 partite
        for combo in combinations(filtered_matches, r):
            top_combinations.append(combo)
    top_combinations = top_combinations[:5]

    # 4️⃣ Invia messaggio Telegram
    send_telegram_message(value_bets, top_combinations)

if __name__ == "__main__":
    main()
