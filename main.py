from odds_api import get_matches
from quantum_model import calculate_quantum_probabilities
from value_bet import find_value
from telegram_bot import send_message

matches = get_matches()

print("Partite trovate:", len(matches))

value_matches = []

for m in matches:

    probs = calculate_quantum_probabilities(m)

    is_value, idx, score = find_value(probs, m["odds"])

    if is_value:

        value_matches.append({
            "match": m["match"],
            "outcome": ["1","X","2"][idx],
            "value": score
        })

print("Value bet trovate:", len(value_matches))

msg = "📊 VALUE BET DEL GIORNO\n\n"

for v in value_matches:

    msg += f"{v['match']} → {v['outcome']} (value {v['value']:.2f})\n"

if value_matches:
    send_message(msg)
