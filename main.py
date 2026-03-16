# main.py
from odds_api import get_all_matches
from quantum_model import calculate_quantum_probabilities
from telegram_bot import send_telegram_message
from itertools import combinations

def main():
    print("START BOT")

    # 1️⃣ Prende tutte le partite dai 5 campionati
    matches = get_all_matches()
    print(f"MATCHES FOUND: {len(matches)}")

    value_bets = []

    # 2️⃣ Calcola probabilità quantistiche e instabilità
    alpha = 1 / 137
    for m in matches:
        probs = calculate_quantum_probabilities(m)
        m['quantum_probs'] = probs
        evs = [probs[i]*m['odds'][i] for i in range(3)]
        m['expected_value'] = max(evs)
        m['instability'] = abs(probs[0]-probs[2])*alpha

        if m['expected_value'] >= 0.99:  # soglia test
            value_bets.append(m)

    print(f"Value bet trovate: {len(value_bets)}")

    # 3️⃣ Genera combinazioni multiple (top 5 per instabilità)
    sorted_matches = sorted(value_bets, key=lambda x: x['instability'], reverse=True)
    top_combinations = []
    for r in [2,3,4]:
        for combo in combinations(sorted_matches, r):
            top_combinations.append(combo)
    # prende solo le prime 5 più instabili
    top_combinations = top_combinations[:5]

    # 4️⃣ Invia Telegram
    send_telegram_message(value_bets, top_combinations)

if __name__ == "__main__":
    main()
