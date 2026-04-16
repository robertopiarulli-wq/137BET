import os
import requests
from supabase import create_client
from datetime import datetime, timedelta, timezone

# Configurazione
FD_KEY = os.environ.get("FOOTBALL_DATA_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ID delle competizioni (es: 2021=Premier, 2019=Serie A, 2014=LaLiga, 2002=Bundes, 2015=Ligue1)
COMPETITIONS = [2021, 2019, 2014, 2002, 2015]

def fetch_and_sync_matches():
    headers = {'X-Auth-Token': FD_KEY}
    
    # --- LOGICA DI AUTO-PULIZIA ---
    # Calcoliamo la data di ieri in formato ISO
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    
    try:
        # Cancella dal DB i match più vecchi di ieri
        supabase.table("matches").delete().lt("match_date", yesterday).execute()
        print("🧹 Pulizia database: match vecchi rimossi con successo.")
    except Exception as e:
        print(f"⚠️ Nota sulla pulizia: {e}")
    # ------------------------------

    for comp in COMPETITIONS:
        url = f"https://api.football-data.org/v4/competitions/{comp}/matches?status=SCHEDULED"
        res = requests.get(url, headers=headers).json()
        
        if 'matches' not in res: continue
        
        for m in res['matches']:
            match_data = {
                "match_id_api": str(m['id']),
                "home_team_name": m['homeTeam']['name'],
                "away_team_name": m['awayTeam']['name'],
                "match_date": m['utcDate'],
                "league": m['competition']['name']
            }
            
            # Upsert su Supabase (Inserisce o aggiorna se match_id_api esiste)
            supabase.table("matches").upsert(match_data, on_conflict="match_id_api").execute()
    
    print("✅ Tabella Matches aggiornata con i prossimi incontri!")

if __name__ == "__main__":
    fetch_and_sync_matches()
