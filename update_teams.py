import os
import requests
from supabase import create_client

SB_URL = os.environ.get("SUPABASE_URL")
SB_KEY = os.environ.get("SUPABASE_KEY")
FD_KEY = os.environ.get("FOOTBALL_DATA_API_KEY") 
supabase = create_client(SB_URL, SB_KEY)

def update_all_teams():
    # Tutte le 10 leghe (Big 5 + 5 Cadette)
    leagues = ['SA', 'PL', 'PD', 'BL1', 'FL1', 'ELC', 'SEC', 'SB', 'G2', 'FL2']
    print(f"🔄 Sincronizzazione Quantistica per {len(leagues)} leghe...")
    
    for league in leagues:
        url = f"https://api.football-data.org/v4/competitions/{league}/standings"
        headers = {'X-Auth-Token': FD_KEY}
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            standings = data.get('standings', [{}])[0].get('table', [])
            
            for entry in standings:
                team_name = entry['team']['shortName']
                played = entry.get('playedGames', 1)
                
                # EVITIAMO IL 1.2 FISSO: Calcoliamo le medie reali
                # Se non hanno ancora giocato, usiamo 1.0 come base neutra
                if played > 0:
                    avg_s = round(entry['goalsFor'] / played, 2)
                    avg_c = round(entry['goalsAgainst'] / played, 2)
                else:
                    avg_s, avg_c = 1.0, 1.0

                raw_form = entry.get('form', 'DDDDD')
                clean_form = raw_form.replace(',', '')[-5:] if raw_form else 'DDDDD'
                
                # UPSERT: Aggiorna se esiste, inserisce se manca
                supabase.table("teams").upsert({
                    "team_name": team_name,
                    "recent_form": clean_form,
                    "avg_scored": avg_s,     # <--- ORA È IL DATO REALE
                    "avg_conceded": avg_c,   # <--- ORA È IL DATO REALE
                    "last_updated": "now()"
                }, on_conflict="team_name").execute()
                
            print(f"✅ {league} sincronizzata con medie reali.")
        except Exception as e:
            print(f"❌ Errore su {league}: {e}")

if __name__ == "__main__":
    update_all_teams()
