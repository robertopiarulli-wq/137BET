# main.py
from odds_api import get_all_matches, extract_match_info
from quantum_model import calculate_quantum_probabilities
from telegram_bot import send_telegram_message
from itertools import combinations
from math import prod

EV_THRESHOLD = 0.99  # soglia Value Bet singole
ALPHA = 1 / 137      # instabilità quantistica

def main():
    print("START BOT")

    # 🔹 Prende tutte le partite disponibili dall'API
    matches = get_all_matches()

    all_matches = []
    value_bets = []

    # 🔹 Calcolo probabilità e EV per tutte le partite (senza filtro data)
    for m in matches:
        home_name, away_name, odds = extract_match_info(m)
        m['home_name'] = home_name
        m['away_name'] = away_name
        m['odds'] = odds

        probs = calculate_quantum_probabilities(m)
        m['quantum_probs'] = probs

        evs = [probs[i] * odds[i] for i in range(3)]
        m['evs'] = evs
        m['expected_value'] = max(evs)
        m['instability'] = abs(probs[0]-probs[2]) * ALPHA

        all_matches.append(m)

        if m['expected_value'] >= EV_THRESHOLD:
            value_bets.append(m)

    print(f"MATCHES FOUND: {len(all_matches)}")
    print(f"Value bet trovate: {len(value_bets)}")

    # 🔹 Combinazioni multiple
    all_combos = []
    for r in [2,3]:
        if len(all_matches) >= r:
            for combo in combinations(all_matches, r):
                ev_combo = prod([m['expected_value'] for m in combo])
                all_combos.append({'matches': combo, 'ev_combined': ev_combo})

    # 🔹 Top 5 combinazioni
    top_combos = sorted(all_combos, key=lambda x: x['ev_combined'], reverse=True)[:5]

    # 🔹 Invia messaggio Telegram
    send_telegram_message(value_bets, top_combos)

if __name__ == "__main__":
    main()
