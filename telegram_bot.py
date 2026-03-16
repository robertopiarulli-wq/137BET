# telegram_bot.py
import os
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(value_bets, top_combinations):
    if not value_bets:
        msg = "Nessuna value bet oggi 🚫"
    else:
        msg = "💰 Value Bet Oggi:\n"
        for m in value_bets[:10]:  # top 10
            probs = m['quantum_probs']
            msg += f"{m['match']} | Odds: {m['odds']} | Probs: {[round(p,2) for p in probs]} | Instab: {round(m['instability'],4)}\n"

        msg += "\n🔝 Top 5 combinazioni multiple:\n"
        for i, combo in enumerate(top_combinations,1):
            combo_text = " + ".join([c['match'] for c in combo])
            msg += f"{i}: {combo_text}\n"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
