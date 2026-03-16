# main.py
from odds_api import get_all_matches
from quantum_model import calculate_quantum_probabilities
from telegram_bot import send_telegram_message

def main():
    print("START BOT")

    # 1. Prende tutte le partite dai 5 campionati
    matches = get_all_matches()
    print(f"MATCHES FOUND: {len(matches)}")

    value_bets = []

    # 2. Calcola probabilità quantistiche
    for m in matches:
        probs = calculate_quantum_probabilities(m)
        m['quantum_probs'] = probs

        # semplice expected value
        odds = m['odds']
        ev_home = probs[0] * odds[0]
        ev_draw = probs[1] * odds[1]
        ev_away = probs[2] * odds[2]

        if max(ev_home, ev_draw, ev_away) > 1.0:  # soglia test
            value_bets.append(m)

    print(f"Partite trovate: {len(matches)}")
    print(f"Value bet trovate: {len(value_bets)}")

    # 3. Invia Telegram
    send_telegram_message(value_bets)

if __name__ == "__main__":
    main()
