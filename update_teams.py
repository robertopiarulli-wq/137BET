import os
import requests
from supabase import create_client

# --- CONFIGURAZIONE ---
SB_URL = os.environ.get("SUPABASE_URL")
SB_KEY = os.environ.get("SUPABASE_KEY")
FD_KEY = os.environ.get("FOOTBALL_DATA_API_KEY") 
supabase = create_client(SB_URL, SB_KEY)

def update_all_teams():
    # Le 10 leghe previste
    leagues = ['SA', 'PL', 'PD', 'BL1', 'FL1', 'ELC', 'SEC', 'SB', 'G2', 'FL2']
    print(f"🔄 Sincronizzazione Avanzata V17 per {len(leagues)} leghe...")
    
    headers = {'X-Auth-Token': FD_KEY}

    for league in leagues:
        try:
            # 1. ANALISI DEI MATCH (Per Clean Sheets e Away Power)
            # Prendiamo gli ultimi 100 match per avere dati recenti e accurati
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

                        # Inizializzazione se non presente
                        for t in [h_team, a_team]:
                            if t not in advanced_stats:
                                advanced_stats[t] = {'cs': 0, 'away_goals': 0, 'away_matches': 0}

                        # Conteggio Clean Sheets (Porta inviolata)
                        if score_a == 0: advanced_stats[h_team]['cs'] += 1
                        if score_h == 0: advanced_stats[a_team]['cs'] += 1
                        
                        # Conteggio Away Power (Gol fatti fuori casa)
                        advanced_stats[a_team]['away_goals'] += score_a
                        advanced_stats[a_team]['away_matches'] += 1

            # 2. ANALISI DELLA CLASSIFICA (Per Medie Generali e Forma)
            url_standings = f"https://api.football-data.org/v4/competitions/{league}/standings"
            response = requests.get(url_standings, headers=headers)
            data = response.json()
            standings = data.get('standings', [{}])[0].get('table', [])
            
            for entry in standings:
                team_name = entry['team']['shortName']
                played = entry.get('playedGames', 1)
                
                # Medie classiche
                if played > 0:
                    avg_s = round(entry['goalsFor'] / played, 2)
                    avg_c = round(entry['goalsAgainst'] / played, 2)
                else:
                    avg_s, avg_c = 1.0, 1.0

                raw_form = entry.get('form', 'DDDDD')
                clean_form = raw_form.replace(',', '')[-5:] if raw_form else 'DDDDD'
                
                # Recupero dati avanzati dal dizionario temporaneo
                st = advanced_stats.get(team_name, {'cs': 0, 'away_goals': 0, 'away_matches': 0})
                
                # Calcolo media gol fuori casa (Away Power)
                avg_away_scored = round(st['away_goals'] / st['away_matches'], 2) if st['away_matches'] > 0 else 0

                # UPSERT su Supabase
                supabase.table("teams").upsert({
                    "team_name": team_name,
                    "recent_form": clean_form,
                    "avg_scored": avg_s,
                    "avg_conceded": avg_c,
                    "clean_sheets": st['cs'],             # <--- NUOVO SEGNALE
                    "goals_scored_away": avg_away_scored, # <--- NUOVO SEGNALE
                    "last_updated": "now()"
                }, on_conflict="team_name").execute()
                
            print(f"✅ {league}: Medie, Clean Sheets e Away Power sincronizzati.")

        except Exception as e:
            print(f"❌ Errore su {league}: {e}")

if __name__ == "__main__":
    update_all_teams()
