# main.py
from odds_api import get_all_matches
from quantum_model import calculate_quantum_probabilities
from telegram_bot import send_telegram_message, get_match_teams
from itertools import combinations
from datetime import datetime, timezone
from math import prod

EV_THRESHOLD = 0.99  # soglia Value Bet singole
alpha = 1 / 137      # instabilità

def main():
    print("START BOT")

    # 🔹 Prende tutte le partite disponibili dall'API
    matches = get_all_matches()

    # 🔹 Filtra solo partite della giornata
    today = datetime.now(timezone.utc).date()
    matches_today = []
    for m in matches:
        if 'commence_time' in m:
            match_time = datetime.fromisoformat(m['commence_time'].replace('Z','+00:00')).date()
            if match_time == today:
                matches_today.append(m)
        else:
            matches_today.append(m)  # fallback

    print(f"MATCHES FOUND TODAY: {len(matches_today)}")

    value_bets = []
    all_matches = []

    # 🔹 Calcolo probabilità quantistiche, EV e instabilità
    for m in matches_today:
        probs = calculate_quantum_probabilities(m)
        m['quantum_probs'] = probs
        evs = [probs[i] * m['odds'][i] for i in range(3)]
        m['evs'] = evs
        m['expected_value'] = max(evs)
        m['instability'] = abs(probs[0] - probs[2]) * alpha
        all_matches.append(m)

        # 🔹 Singole Value Bet
        if m['expected_value'] >= EV_THRESHOLD:
            value_bets.append(m)

    print(f"Value bet trovate: {len(value_bets)}")

    # 🔹 Genera combinazioni multiple da tutte le partite
    all_combos = []
    for r in [2,3]:
        for combo in combinations(all_matches, r):
            ev_combo = prod([m['expected_value'] for m in combo])
            all_combos.append({'matches': combo, 'ev_combined': ev_combo})

    # 🔹 Ordina top 5 combinazioni per EV combinato
    top_combos = sorted(all_combos, key=lambda x: x['ev_combined'], reverse=True)[:5]

    # 🔹 Invia messaggio Telegram
    send_telegram_message(value_bets, top_combos)

if __name__ == "__main__":
    main()
