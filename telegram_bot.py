# telegram_bot.py
import os
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(value_bets, top_combos):
    msg = ""

    # 🔹 Singole Value Bet
    if not value_bets:
        msg += "⚪ Nessuna Value Bet oggi\n\n"
    else:
        msg += "💰 Value Bet singole:\n\n"
        for m in value_bets[:10]:
            probs = m['quantum_probs']
            evs = m['evs']
            outcomes = ["Home", "Draw", "Away"]
            max_index = evs.index(max(evs))
            suggested = outcomes[max_index]

            # Evita Draw se EV troppo vicino
            if suggested == "Draw" and (abs(evs[0]-evs[1])<0.05 or abs(evs[2]-evs[1])<0.05):
                suggested = "Home" if evs[0] > evs[2] else "Away"

            home = m['teams'][0] if 'teams' in m else "Team1"
            away = m['teams'][1] if 'teams' in m else "Team2"

            msg += f"🟢 {home} vs {away} ➡ {suggested}\n"
            msg += f"Quote: {m['odds']}\n"
            msg += f"EV: {[round(e,2) for e in evs]} | α: {round(m['instability'],4)}\n\n"

    # 🔹 Top 5 combinazioni multiple
    msg += "🔝 Top 5 combinazioni multiple:\n\n"
    for i, combo_dict in enumerate(top_combos, 1):
        combo_text = ""
        for c in combo_dict['matches']:
            probs = c['quantum_probs']
            evs = c['evs']
            outcomes = ["Home", "Draw", "Away"]
            max_index = evs.index(max(evs))
            suggested = outcomes[max_index]

            if suggested == "Draw" and (abs(evs[0]-evs[1])<0.05 or abs(evs[2]-evs[1])<0.05):
                suggested = "Home" if evs[0] > evs[2] else "Away"

            home = c['teams'][0] if 'teams' in c else "Team1"
            away = c['teams'][1] if 'teams' in c else "Team2"

            combo_text += f"{home} vs {away} ➡ {suggested} (EV: {round(evs[max_index],2)}) + "

        combo_text = combo_text.rstrip(" + ")
        msg += f"{i}: {combo_text} | EV combinato: {round(combo_dict['ev_combined'],2)}\n"

    # 🔹 Invia Telegram
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
