import os
import requests
from supabase import create_client

# Configurazione
SB_URL = os.environ.get("SUPABASE_URL")
SB_KEY = os.environ.get("SUPABASE_KEY")
FD_KEY = os.environ.get("FOOTBALL_DATA_API_KEY") # La tua chiave API
supabase = create_client(SB_URL, SB_KEY)

def get_recent_form_and_stats():
    # 1. Chiamata all'API per ottenere le classifiche e la forma
    # Esempio per la Serie A (codice 'SA')
    leagues = ['SA', 'PL', 'PD', 'BL1', 'FL1']
    
    for league in leagues:
        url = f"https://api.football-data.org/v4/competitions/{league}/standings"
        headers = {'X-Auth-Token': FD_KEY}
        response = requests.get(url, headers=headers).json()
        
        for table in response.get('standings', [])[0].get('table', []):
            team_name = table['team']['shortName']
            form = table.get('form', 'DDDDD').replace(',', '') # Trasforma 'W,L,W' in 'WLW'
            
            # 2. Aggiorna Supabase
            supabase.table("teams").update({
                "recent_form": form[-5:], # Prende solo le ultime 5
                "last_updated": "now()"
            }).eq("team_name", team_name).execute()

if __name__ == "__main__":
    get_recent_form_and_stats()
