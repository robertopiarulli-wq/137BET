import os
import requests
from supabase import create_client
from datetime import datetime

# --- CONFIGURAZIONE ---
SB_URL = os.environ.get("SUPABASE_URL")
SB_KEY = os.environ.get("SUPABASE_KEY")
FD_KEY = os.environ.get("FOOTBALL_DATA_API_KEY") 
supabase = create_client(SB_URL, SB_KEY)

def clean_team_name(name):
    """Normalizza i nomi delle squadre per evitare duplicati sporchi"""
    if not name: return ""
    # Rimuove suffissi comuni che generano doppioni
    to_remove = [" FC", " 1909", " AFC", " AS", " AC", "BSC ", " CF"]
    cleaned = name
    for word in to_remove:
        cleaned = cleaned.replace(word, "")
    return cleaned.strip()

def calculate_sigma(results, matches_data):
    """
    Calcola la rugosità sigma (s3):
    0: Risultati identici (es. 3 vittorie)
    1.5: Instabilità estrema (es. una vittoria larga e una sconfitta pesante)
    1: Risultati misti
    """
    if len(results) < 3: return 1.0
    
    # Se tutti i risultati sono uguali (es. WWW o DDD)
    if len(set(results)) == 1:
        return 0.0
    
    # Controllo instabilità estrema (Score-based)
    has_big_win = False
    has_loss = 'L' in results
    for m in matches_data:
        diff = abs(m['score']['fullTime']['home'] - m['score']['fullTime']['away'])
        if diff >= 3 and (m['res'] == 'W'):
            has_big_win = True
            
    if has_big_win and has_loss:
        return 1.5
        
    return 1.0

def update_all_teams():
    leagues = ['SA', 'PL', 'PD', 'BL1', 'FL1', 'ELC', 'SEC', 'SB', 'G2', 'FL2']
    print(f"🔄 Sincronizzazione V17.2 (Quantum-Parisi Edition) per {len(leagues)} leghe...")
    
    headers = {'X-Auth-Token': FD_KEY}

    for league in leagues:
        try:
            # 1. RECUPERO MATCH PER ANALISI AVANZATA E PARISI
            url_matches = f"https://api.football-data.org/v4/competitions/{league}/matches"
            res_m = requests.get(url_matches, headers=headers).json()
            
            advanced_stats = {}
            team_matches_history = {} # Per calcolare p3, g3_f, g3_s, s3

            if 'matches' in res_m:
                # Ordiniamo i match dal più recente al più vecchio
                sorted_matches = sorted(res_m['matches'], key=lambda x: x['utcDate'], reverse=True)
                
                for m in sorted_matches:
                    if m['status'] == 'FINISHED':
                        h_team = clean_team_name(m['homeTeam']['shortName'])
                        a_team = clean_team_name(m['awayTeam']['shortName'])
                        gh = m['score']['fullTime']['home']
                        ga = m['score']['fullTime']['away']

                        # Statistiche Generali (CS e Away Power)
                        for t in [h_team, a_team]:
                            if t not in advanced_stats:
                                advanced_stats[t] = {'cs': 0, 'away_goals': 0, 'away_matches': 0}
                            if t not in team_matches_history:
                                team_matches_history[t] = []

                        if ga == 0: advanced_stats[h_team]['cs'] += 1
                        if gh == 0: advanced_stats[a_team]['cs'] += 1
                        advanced_stats[a_team]['away_goals'] += ga
                        advanced_stats[a_team]['away_matches'] += 1

                        # Archiviazione per analisi Parisi (Ultime 3)
                        if len(team_matches_history[h_team]) < 3:
                            res = 'W' if gh > ga else ('D' if gh == ga else 'L')
                            team_matches_history[h_team].append({'res': res, 'gf': gh, 'gs': ga, 'score': m['score']})
                        
                        if len(team_matches_history[a_team]) < 3:
                            res = 'W' if ga > gh else ('D' if ga == gh else 'L')
                            team_matches_history[a_team].append({'res': res, 'gf': ga, 'gs': gh, 'score': m['score']})

            # 2. ANALISI CLASSIFICA E UPSERT
            url_standings = f"https://api.football-data.org/v4/competitions/{league}/standings"
            data = requests.get(url_standings, headers=headers).json()
            standings = data.get('standings', [{}])[0].get('table', [])
            
            for entry in standings:
                team_name = clean_team_name(entry['team']['shortName'])
                played = entry.get('playedGames', 1)
                
                avg_s = round(float(entry['goalsFor'] / played), 2) if played > 0 else 1.0
                avg_c = round(float(entry['goalsAgainst'] / played), 2) if played > 0 else 1.0
                
                # --- FIX FORMA (GESTIONE NONE) ---
                raw_form = entry.get('form')
                if raw_form is None:
                    clean_form = 'DDDDD'
                else:
                    clean_form = str(raw_form).replace(',', '')[-5:]
                
                # Recupero dati Parisi Index
                history = team_matches_history.get(team_name, [])
                p3 = sum({'W': 3, 'D': 1, 'L': 0}[m['res']] for m in history)
                g3_f = sum(m['gf'] for m in history)
                g3_s = sum(m['gs'] for m in history)
                s3 = calculate_sigma([m['res'] for m in history], history)

                st = advanced_stats.get(team_name, {'cs': 0, 'away_goals': 0, 'away_matches': 0})
                avg_away_scored = round(float(st['away_goals'] / st['away_matches']), 2) if st['away_matches'] > 0 else 0.0

                supabase.table("teams").upsert({
                    "team_name": team_name,
                    "recent_form": clean_form,
                    "avg_scored": avg_s,
                    "avg_conceded": avg_c,
                    "clean_sheets": int(st['cs']),
                    "goals_scored_away": float(avg_away_scored),
                    "p3": float(p3),
                    "g3_f": float(g3_f),
                    "g3_s": float(g3_s),
                    "s3": float(s3),
                    "last_updated": "now()"
                }, on_conflict="team_name").execute()
                
            print(f"✅ {league} sincronizzata con metriche Parisi.")

        except Exception as e:
            print(f"❌ Errore su {league}: {e}")

if __name__ == "__main__":
    update_all_teams()
