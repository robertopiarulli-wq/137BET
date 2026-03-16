# telegram_bot.py
import os
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(value_bets, top_combinations):
    msg = ""

    # 🔹 Sezione singole Value Bet
    if not value_bets:
        msg += "Nessuna Value Bet oggi ⚪\n\n"
    else:
        msg += "💰 Value Bet Oggi:\n\n"
        for m in value_bets[:10]:  # top 10
            probs = m['quantum_probs']
            evs = m['evs']
            msg += f"🟢 {m['match']}\n"
            msg += f"Quote: {m['odds']}\n"
            msg += f"Probs: {[round(p,2) for p in probs]}\n"
            msg += f"EV: {[round(e,2) for e in evs]}\n"
            msg += f"Instab α: {round(m['instability'],4)}\n\n"

    # 🔹 Sezione top 5 combinazioni multiple
    msg += "🔝 Top 5 combinazioni multiple:\n"
    for i, combo in enumerate(top_combinations, 1):
        combo_text = " + ".join([c['match'] for c in combo])
        msg += f"{i}: {combo_text}\n"

    # 🔹 Invia messaggio Telegram
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
