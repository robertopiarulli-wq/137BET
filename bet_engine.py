def run_analysis():
    # ... (caricamento dati precedente) ...
    
    # Dizionario per memorizzare solo il miglior segno per ogni match
    best_signs_by_match = {}
    
    for m in matches:
        # Calcolo p1, px, p2, p_over
        # ... (logica get_full_analysis esistente) ...
        
        # Analisi 1X2 e Gol
        possible_bets = [
            ('1', p1, m['odds_1']), ('X', px, m['odds_x']), ('2', p2, m['odds_2']),
            ('Over 2.5', p_over, 1.90), ('Under 2.5', 1-p_over, 1.90)
        ]
        
        match_name = f"{m['home_team_name']} vs {m['away_team_name']}"
        
        # Filtro: teniamo solo il miglior segno per questo specifico match (con EV > 0)
        best_ev_for_match = -1.0
        best_bet_data = None
        
        for segno, prob, quota in possible_bets:
            ev = (prob * quota) - 1
            if ev > best_ev_for_match:
                best_ev_for_match = ev
                best_bet_data = {"match": match_name, "segno": segno, "ev": ev, "quota": quota}
        
        if best_ev_for_match > 0:
            best_signs_by_match[match_name] = best_bet_data

    # Trasformiamo in lista ordinata per EV
    candidates = sorted(best_signs_by_match.values(), key=lambda x: x['ev'], reverse=True)
    
    # 1. Messaggio Singole
    msg = "📈 *TOP 10 SINGOLE DI VALORE (UNIVOCHE)*\n\n"
    for b in candidates[:10]:
        msg += f"🏟 {b['match']} | *{b['segno']}* @{b['quota']} (EV: {round(b['ev']*100,1)}%)\n"
    
    # 2. Tripla (Ora garantita senza doppioni dello stesso match)
    tripla_cands = candidates[:3]
    if len(tripla_cands) >= 3:
        total_odds = 1.0
        for b in tripla_cands: total_odds *= b['quota']
        msg += "\n\n🚀 *SCHEDINA OTTIMIZZATA (TRIPLA)*\n\n"
        for b in tripla_cands:
            msg += f"🏟 {b['match']} -> *{b['segno']}* @{b['quota']}\n"
        msg += f"\n💰 Quota Totale: *{round(total_odds, 2)}*"
    
    send_telegram_msg(msg)
