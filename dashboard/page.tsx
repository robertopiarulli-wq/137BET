"use client";
import { useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export default function Dashboard137Bet() {
  const [predictions, setPredictions] = useState([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetchPredictions();
  }, [search]);

  async function fetchPredictions() {
    let query = supabase
      .from('prediction_history_137bet')
      .select('*')
      .order('ranking_power', { ascending: false });

    if (search) {
      query = query.or(`match_name.ilike.%${search}%,match_date.ilike.%${search}%`);
    }

    const { data } = await query;
    setPredictions(data || []);
  }

  const getRankColor = (power) => {
    if (power >= 80) return 'bg-emerald-500 text-white'; // Top Power
    if (power >= 65) return 'bg-blue-500 text-white';    // Solid
    return 'bg-amber-500 text-white';                   // Caution
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white p-4 font-sans">
      <header className="max-w-4xl mx-auto mb-8 text-center">
        <h1 className="text-3xl font-bold text-emerald-400">🏆 137BET QUANTUM DASH</h1>
        <p className="text-slate-400">V18.3 - Ranking & Linear Distance Analysis</p>
      </header>

      <div className="max-w-4xl mx-auto mb-6">
        <input
          type="text"
          placeholder="Cerca squadra o data (es: 25/04)..."
          className="w-full p-4 rounded-lg bg-slate-800 border border-slate-700 focus:ring-2 focus:ring-emerald-500 outline-none"
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="max-w-4xl mx-auto grid gap-4">
        {predictions.map((pred) => (
          <div key={pred.id} className="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-lg">
            <div className="flex justify-between items-start mb-3">
              <div>
                <span className="text-xs text-slate-400 block">{pred.match_date}</span>
                <h2 className="text-xl font-bold">{pred.match_name}</h2>
              </div>
              <div className={`px-4 py-2 rounded-lg font-black text-xl ${getRankColor(pred.ranking_power)}`}>
                {pred.ranking_sign}
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center border-t border-slate-700 pt-3">
              <div>
                <span className="text-xs text-slate-500 uppercase block">Quantum Rank</span>
                <span className="font-mono text-emerald-400">{pred.ranking_power}%</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 uppercase block">Delta PP</span>
                <span className="font-mono text-blue-400">{pred.pp_diff}</span>
              </div>
              <div className="col-span-2">
                <span className="text-xs text-slate-500 uppercase block">Sentenza Parisi</span>
                <span className="text-sm font-semibold text-slate-200">{pred.pp_sentenza}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
