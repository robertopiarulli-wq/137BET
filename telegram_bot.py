# telegram_bot.py
import os
import requests
from functools import reduce

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(value_bets, top_combinations):
    msg = ""

    # 🔹 Singole Value Bet
    if not value_bets:
        msg += "⚪ Nessuna Value Bet oggi\n\n"
    else:
        msg += "💰 Value Bet Oggi:\n\n"
        for m in value_bets[:10]:
            probs = m['quantum_probs']
            evs = m['evs']
            outcomes = ["Home", "Draw", "Away"]

            max_index = evs.index(max(evs))
            suggested = outcomes[max_index]
            if suggested == "Draw" and (abs(evs[0]-evs[1])<0.05 or abs(evs[2]-evs[1])<0.05):
                suggested = "Home" if evs[0] > evs[2] else "Away"

            msg += f"🟢 {m['match']}\n"
            msg += f"Quote: {m['odds']}\n"
            msg += f"Probs: {[round(p,2) for p in probs]}\n"
            msg += f"EV: {[round(e,2) for e in evs]} | Suggerito: {suggested}\n"
            msg += f"Instab α: {round(m['instability'],4)}\n\n"

    # 🔹 Top 5 combinazioni multiple
    msg += "🔝 Top 5 combinazioni multiple:\n\n"
    for i, combo in enumerate(top_combinations, 1):
        combo_text = ""
        ev_combo = 1.0
        for c in combo:
            probs = c['quantum_probs']
            evs = c['evs']
            outcomes = ["Home", "Draw", "Away"]
            max_index = evs.index(max(evs))
            suggested = outcomes[max_index]

            if suggested == "Draw" and (abs(evs[0]-evs[1])<0.05 or abs(evs[2]-evs[1])<0.05):
                suggested = "Home" if evs[0] > evs[2] else "Away"
                max_index = 0 if evs[0] > evs[2] else 2

            ev_combo *= evs[max_index]
            combo_text += f"{c['match']} ➡ {suggested} (EV: {round(evs[max_index],2)}) + "

        combo_text = combo_text.rstrip(" + ")
        msg += f"{i}: {combo_text} | EV combinato: {round(ev_combo,2)}\n"

    # 🔹 Invia Telegram
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
