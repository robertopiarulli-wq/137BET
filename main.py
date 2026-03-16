import numpy as np
import logging
import matplotlib.pyplot as plt

from api_handler import get_daily_odds
from quantum_model import calculate_quantum_probabilities
from instability import calc_instability_score
from multiples import generate_multiple_matrix, apply_pauli_filter
from telegram_bot import send_message, send_photo

# Setup logging
logging.basicConfig(filename="bot.log", level=logging.INFO, format="%(asctime)s - %(message)s")

partite = get_daily_odds()
partite_instabili = []

for p in partite:
    prob_model = calculate_quantum_probabilities(p)
    instability = calc_instability_score(prob_model, p)
    if np.any(instability > 1):
        p["prob_model"] = prob_model
        p["instability"] = instability
        partite_instabili.append(p)
        logging.info(f"{p['match']} instabile")

if partite_instabili:
    matrix = generate_multiple_matrix([p["prob_model"] for p in partite_instabili])
    matrix_filtrata = apply_pauli_filter(matrix)
else:
    matrix_filtrata = []

logging.info(f"Combinazioni consigliate: {len(matrix_filtrata)}")

def calculate_value_bets(prob_model, odds):
    value = prob_model * np.array(odds) - 1
    idx = np.argmax(value)
    return value, idx

def create_dashboard_image(partite_instabili, matrix_filtrata, filename="dashboard.png"):
    matches = [p["match"] for p in partite_instabili]
    instability_vals = [np.max(p["instability"]) for p in partite_instabili]
    value_indices = [np.argmax(calculate_value_bets(p["prob_model"], p["odds"])[0]) for p in partite_instabili]

    colors = ["#1f77b4" if idx == 0 else "#ff7f0e" if idx == 1 else "#2ca02c" for idx in value_indices]

    plt.figure(figsize=(10,5))
    bars = plt.barh(matches, instability_vals, color=colors)
    for bar, score in zip(bars, instability_vals):
        plt.text(bar.get_width()+0.1, bar.get_y()+0.3, f"{score:.2f}")
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    return filename

def format_message(partite_instabili, matrix_filtrata):
    msg = "*⚡ Partite Instabili con Value Bet ⚡*\n"
    msg += "🏟 Match | 1️⃣ | ⚖️ X | 2️⃣ | Instability | 💎 VB\n"
    msg += "-------------------------\n"
    for p in partite_instabili:
        values, idx = calculate_value_bets(p["prob_model"], p["odds"])
        msg += f"{p['match']} | {p['prob_model'][0]:.2f}{'*' if idx==0 else ''} | {p['prob_model'][1]:.2f}{'*' if idx==1 else ''} | {p['prob_model'][2]:.2f}{'*' if idx==2 else ''} | {np.max(p['instability']):.2f} | {idx+1}\n"
    msg += f"\n🎯 Combinazioni consigliate: {len(matrix_filtrata)}"
    return msg

if partite_instabili:
    send_message(format_message(partite_instabili, matrix_filtrata))
    img_file = create_dashboard_image(partite_instabili, matrix_filtrata)
    send_photo(img_file)
