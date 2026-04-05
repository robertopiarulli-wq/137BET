import os
import requests
from supabase import create_client
from datetime import datetime, timezone

supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
FD_KEY = os.environ.get("FOOTBALL_DATA_API_KEY")

def verify_and_score():
    # Prendi i match non ancora verificati
    pending = supabase.table("predictions_history").select("*").is_("actual_result", "null").execute().data
    
    if not pending:
        print("Tutti i match sono già stati verificati.")
        return

    # Usiamo l'API per prendere i risultati recenti (ultimi 3 giorni)
    url = "https://api.football-data.org/v4/matches"
    headers = {'X-Auth-Token': FD_KEY}
    r = requests.get(url, headers=headers).json()
    finished_matches = r.get('matches', [])

    for pred in pending:
        # Cerchiamo il match nei risultati dell'API
        for mf in finished_matches:
            if mf['status'] == 'FINISHED':
                # Matching semplice per nome squadra
                if mf['homeTeam']['shortName'] in pred['match_name']:
                    score_h = mf['score']['fullTime']['home']
                    score_a = mf['score']['fullTime']['away']
                    
                    actual = "X"
                    if score_h > score_a: actual = "1"
                    if score_a > score_h: actual = "2"
                    
                    is_correct = (actual == pred['predicted_sign'])
                    
                    # Aggiorna il record in Supabase
                    supabase.table("predictions_history").update({
                        "actual_result": actual,
                        "is_correct": is_correct
                    }).eq("id", pred['id']).execute()
                    
                    print(f"✅ Verificato: {pred['match_name']} -> Risultato: {actual} (Preso: {is_correct})")

if __name__ == "__main__":
    verify_and_score()
