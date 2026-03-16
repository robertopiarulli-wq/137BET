# main.py
from odds_api import get_all_matches
from quantum_model import calculate_quantum_probabilities
from telegram_bot import send_telegram_message
from itertools import combinations
from datetime import datetime, timezone

INSTABILITY_THRESHOLD = 0.005  # soglia minima instabilità α

def main():
    print("START BOT")

    # 🔹 Prende tutte le partite disponibili dall'API
    matches = get_all_matches()

    # 🔹 Filtra solo partite della giornata (robusto se manca commence_time)
    today = datetime.now(timezone.utc).date()
    matches_today = []
    for m in matches:
        if 'commence_time' in m:
            match_time = datetime.fromisoformat(m['commence_time'].replace('Z','+00:00')).date()
            if match_time == today:
                matches_today.append(m)
        else:
            # Fall-back: considera comunque la partita
            matches_today.append(m)

    print(f"MATCHES FOUND TODAY: {len(matches_today)}")

    value_bets = []
    all_matches = []

    alpha = 1 / 137  # instabilità

    # 🔹 Calcolo probabilità quantistiche, EV e instabilità
    for m in matches_today:
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

    # 🔹 Filtra solo partite instabili per combinazioni multiple
    filtered_matches = [m for m in all_matches if m['instability'] > INSTABILITY_THRESHOLD]

    # 🔹 Genera combinazioni multiple top 5 (2 o 3 partite)
    top_combinations = []
    for r in [2,3]:
        for combo in combinations(filtered_matches, r):
            top_combinations.append(combo)
    top_combinations = top_combinations[:5]

    # 🔹 Invia messaggio Telegram
    send_telegram_message(value_bets, top_combinations)

if __name__ == "__main__":
    main()
