import os
import requests
from supabase import create_client

# --- CONFIGURAZIONE ---
SB_URL = os.environ.get("SUPABASE_URL")
SB_KEY = os.environ.get("SUPABASE_KEY")
FD_KEY = os.environ.get("FOOTBALL_DATA_API_KEY") 
supabase = create_client(SB_URL, SB_KEY)

def update_all_teams():
    leagues = ['SA', 'PL', 'PD', 'BL1', 'FL1', 'ELC', 'SEC', 'SB', 'G2', 'FL2']
    print(f"🔄 Sincronizzazione Avanzata V17 (Fix Types) per {len(leagues)} leghe...")
    
    headers = {'X-Auth-Token': FD_KEY}

    for league in leagues:
        try:
            # 1. ANALISI MATCH (Clean Sheets e Away Goals)
            url_matches = f"https://api.football-data.org/v4/competitions/{league}/matches"
            res_m = requests.get(url_matches, headers=headers).json()
            advanced_stats = {}

            if 'matches' in res_m:
                for m in res_m['matches']:
                    if m['status'] == 'FINISHED':
                        h_team = m['homeTeam']['shortName']
                        a_team = m['awayTeam']['shortName']
                        score_h = m['score']['fullTime']['home']
                        score_a = m['score']['fullTime']['away']

                        for t in [h_team, a_team]:
                            if t not in advanced_stats:
                                advanced_stats[t] = {'cs': 0, 'away_goals': 0, 'away_matches': 0}

                        if score_a == 0: advanced_stats[h_team]['cs'] += 1
                        if score_h == 0: advanced_stats[a_team]['cs'] += 1
                        
                        advanced_stats[a_team]['away_goals'] += score_a
                        advanced_stats[a_team]['away_matches'] += 1

            # 2. ANALISI CLASSIFICA
            url_standings = f"https://api.football-data.org/v4/competitions/{league}/standings"
            data = requests.get(url_standings, headers=headers).json()
            standings = data.get('standings', [{}])[0].get('table', [])
            
            for entry in standings:
                team_name = entry['team']['shortName']
                played = entry.get('playedGames', 1)
                
                avg_s = round(float(entry['goalsFor'] / played), 2) if played > 0 else 1.0
                avg_c = round(float(entry['goalsAgainst'] / played), 2) if played > 0 else 1.0

                raw_form = entry.get('form', 'DDDDD')
                clean_form = raw_form.replace(',', '')[-5:] if raw_form else 'DDDDD'
                
                st = advanced_stats.get(team_name, {'cs': 0, 'away_goals': 0, 'away_matches': 0})
                
                # Calcolo media AWAY esplicito come float
                avg_away_scored = round(float(st['away_goals'] / st['away_matches']), 2) if st['away_matches'] > 0 else 0.0

                supabase.table("teams").upsert({
                    "team_name": team_name,
                    "recent_form": clean_form,
                    "avg_scored": avg_s,
                    "avg_conceded": avg_c,
                    "clean_sheets": int(st['cs']),             # Forza intero per CS
                    "goals_scored_away": float(avg_away_scored), # Forza float per Away Power
                    "last_updated": "now()"
                }, on_conflict="team_name").execute()
                
            print(f"✅ {league} sincronizzata con successo.")

        except Exception as e:
            print(f"❌ Errore su {league}: {e}")

if __name__ == "__main__":
    update_all_teams()
