# telegram_bot.py
import os
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 🔹 Estrazione nomi squadre dai bookmaker
def get_match_teams(match):
    try:
        # prendi primo bookmaker
        bookmakers = match.get('bookmakers', [])
        if not bookmakers:
            return "Team1", "Team2"
        
        # prendi mercato h2h
        markets = bookmakers[0].get('markets', [])
        h2h_market = next((m for m in markets if m['key'] == 'h2h'), None)
        if not h2h_market:
            return "Team1", "Team2"
        
        # prendi i primi due outcomes non Draw
        outcomes = [o['name'] for o in h2h_market.get('outcomes', []) if o['name'].lower() != 'draw']
        if len(outcomes) >= 2:
            return outcomes[0], outcomes[1]
        
        return "Team1", "Team2"
    except Exception:
        return "Team1", "Team2"

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

            home, away = get_match_teams(m)
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

            home, away = get_match_teams(c)
            combo_text += f"{home} vs {away} ➡ {suggested} (EV: {round(evs[max_index],2)}) + "

        combo_text = combo_text.rstrip(" + ")
        msg += f"{i}: {combo_text} | EV combinato: {round(combo_dict['ev_combined'],2)}\n"

    # 🔹 Invia Telegram
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
