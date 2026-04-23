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
    // CORREZIONE 1: Ordiniamo per ranking_power decrescente (Z-A)
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

  // Funzione di utilità per pulire la data visivamente
  const formatDisplayDate = (dateStr) => {
    if (!dateStr) return "N.D.";
    if (dateStr.includes('T')) {
      return dateStr.split('T')[0]; // Prende solo YYYY-MM-DD
    }
    return dateStr; // Restituisce il formato corto se è già così
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-white p-4 md:p-8 font-sans">
      <div className="max-w-5xl mx-auto">
        <header className="flex flex-col md:flex-row justify-between items-center mb-10 border-b border-slate-700 pb-6 gap-4">
          <div>
            <h1 className="text-4xl font-extrabold bg-gradient-to-r from-emerald-400 to-blue-500 bg-clip-text text-transparent">
              🏆 137BET QUANTUM DASH
            </h1>
            <p className="text-slate-400 font-medium tracking-wide">V18.9 Platinum • Parisi/KPZ Engine</p>
          </div>
          <input
            type="text"
            placeholder="🔍 Cerca squadra o data..."
            className="w-full md:w-80 p-3 rounded-xl bg-slate-800 border border-slate-600 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none transition-all shadow-inner"
            onChange={(e) => setSearch(e.target.value)}
          />
        </header>

        <div className="grid grid-cols-1 gap-6">
          {predictions.map((pred) => (
            <div key={pred.id} className="bg-slate-800/40 backdrop-blur-md p-6 rounded-2xl border border-slate-700 hover:border-emerald-500/50 transition-all shadow-2xl group">
              <div className="flex flex-col md:flex-row justify-between gap-6">
                
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="px-3 py-1 rounded-full bg-slate-700 text-[11px] font-bold text-emerald-400 border border-slate-600 uppercase tracking-tighter">
                      {/* CORREZIONE 2: Data pulita */}
                      {formatDisplayDate(pred.match_date)}
                    </span>
                    {pred.ranking_power >= 80 && (
                      <span className="text-[10px] font-black bg-emerald-500 text-slate-900 px-2 py-0.5 rounded animate-pulse">
                        TOP PICK
                      </span>
                    )}
                  </div>
                  <h2 className="text-2xl font-black tracking-tight text-slate-100 group-hover:text-emerald-400 transition-colors">
                    {pred.match_name}
                  </h2>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-sm text-slate-400 italic">Sentenza PP:</span>
                    <span className="text-sm font-bold text-blue-400 uppercase tracking-wide">{pred.pp_sentenza}</span>
                  </div>
                </div>

                <div className="flex gap-2 items-center">
                  <div className="bg-slate-900/80 p-4 rounded-2xl border border-slate-700 flex items-center gap-6 shadow-inner">
                    <div className="text-center px-2">
                      <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold block mb-1 text-center">Rank</span>
                      <span className={`text-3xl font-black leading-none ${pred.ranking_power >= 70 ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {pred.ranking_power ? `${Math.round(pred.ranking_power)}%` : '??'}
                      </span>
                    </div>
                    <div className="h-10 w-[1px] bg-slate-700"></div>
                    <div className="text-center px-2">
                      <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold block mb-1 text-center">Dash Sign</span>
                      <span className="text-3xl font-black leading-none text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]">
                        {/* CORREZIONE 3: Mapping colonna segno */}
                        {pred.ranking_sign || '-'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-700/50 flex flex-wrap justify-between items-center gap-4">
                <div className="flex gap-8">
                   <div className="flex flex-col">
                      <span className="text-[10px] text-slate-500 uppercase font-bold">Delta PP</span>
                      <span className="font-mono text-sm text-slate-300">{pred.pp_diff}</span>
                   </div>
                   <div className="flex flex-col">
                      <span className="text-[10px] text-slate-500 uppercase font-bold">Pauli Advice</span>
                      <span className="text-xs font-semibold text-slate-300">{pred.pauli_advice}</span>
                   </div>
                   <div className="flex flex-col">
                      <span className="text-[10px] text-slate-500 uppercase font-bold">Prob (1-X-2)</span>
                      <span className="text-[11px] font-mono text-slate-400">
                        {Math.round(pred.prob_1 * 100)}% - {Math.round(pred.prob_x * 100)}% - {Math.round(pred.prob_2 * 100)}%
                      </span>
                   </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xl filter drop-shadow-md">{pred.stars}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
