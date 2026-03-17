import os
import requests
from supabase import create_client

# Credenziali dalle variabili d'ambiente di GitHub
SB_URL = os.environ.get("SUPABASE_URL")
SB_KEY = os.environ.get("SUPABASE_KEY")
FD_KEY = os.environ.get("FOOTBALL_DATA_API_KEY") 

supabase = create_client(SB_URL, SB_KEY)

def update_all_teams():
    # Codici dei Big 5 su Football-Data
    leagues = ['SA', 'PL', 'PD', 'BL1', 'FL1']
    
    print("🔄 Inizio aggiornamento forma squadre...")
    
    for league in leagues:
        url = f"https://api.football-data.org/v4/competitions/{league}/standings"
        headers = {'X-Auth-Token': FD_KEY}
        
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            
            # Entriamo nella struttura dei dati: Standings -> Table
            standings = data.get('standings', [{}])[0].get('table', [])
            
            for entry in standings:
                team_name = entry['team']['shortName']
                # Football-Data restituisce la forma come 'W,D,L,W,W'
                raw_form = entry.get('form', 'DDDDD')
                clean_form = raw_form.replace(',', '')[-5:] # Puliamo e prendiamo le ultime 5
                
                # Aggiorniamo Supabase
                supabase.table("teams").update({
                    "recent_form": clean_form,
                    "last_updated": "now()"
                }).eq("team_name", team_name).execute()
                
            print(f"✅ {league} aggiornata.")
            
        except Exception as e:
            print(f"❌ Errore su {league}: {e}")

if __name__ == "__main__":
    update_all_teams()
