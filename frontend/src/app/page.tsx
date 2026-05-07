'use client';
import { useState, useEffect } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Lead {
  id: string;
  org_name: string;
  source: string;
  trigger_categories: string[];
  forced_spend_categories: string[];
  opportunity_score: number;
  severity: number;
  sales_angle: string;
  why_now: string;
  buyer_segments: string[];
  created_at: string;
  external_id?: string;
}

interface Summary {
  total_leads: number;
  high_priority_leads: number;
  avg_opportunity_score: number;
  by_source: Record<string, number>;
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 70 ? 'bg-red-500' : score >= 40 ? 'bg-yellow-500' : 'bg-blue-400';
  return (
    <span className={`${color} text-white text-xs font-bold px-2 py-1 rounded-full`}>
      {score}
    </span>
  );
}

function LeadCard({ lead }: { lead: Lead }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-bold text-gray-900 text-lg">{lead.org_name}</h3>
          <span className="text-xs text-gray-500 uppercase tracking-wide">{lead.source.replace('_', ' ')}</span>
        </div>
        <ScoreBadge score={lead.opportunity_score} />
      </div>
      <div className="mb-3">
        <div className="flex flex-wrap gap-1 mb-2">
          {lead.trigger_categories?.map(cat => (
            <span key={cat} className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded">
              {cat.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-1">
          {lead.forced_spend_categories?.slice(0, 3).map(cat => (
            <span key={cat} className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded">
              {cat.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      </div>
      <div className="border-t border-gray-100 pt-3 space-y-1">
        <p className="text-sm text-gray-700"><span className="font-semibold">Why now:</span> {lead.why_now}</p>
        <p className="text-sm text-gray-700"><span className="font-semibold">Sales angle:</span> {lead.sales_angle}</p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [search, setSearch] = useState('');
  const [source, setSource] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);

  const fetchLeads = async () => {
    try {
      const params = new URLSearchParams();
      if (minScore > 0) params.set('min_score', String(minScore));
      if (source) params.set('source', source);
      const url = search
        ? `${API}/search/leads?q=${encodeURIComponent(search)}&${params}`
        : `${API}/leads/?${params}`;
      const res = await fetch(url);
      const data = await res.json();
      setLeads(data.results || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const res = await fetch(`${API}/leads/stats/summary`);
      const data = await res.json();
      setSummary(data);
    } catch (e) {}
  };

  const triggerIngestion = async (src: string) => {
    setIngesting(true);
    try {
      await fetch(`${API}/ingestion/run/${src}`, { method: 'POST' });
      setTimeout(() => { fetchLeads(); fetchSummary(); setIngesting(false); }, 3000);
    } catch (e) { setIngesting(false); }
  };

  useEffect(() => { fetchLeads(); fetchSummary(); }, [search, source, minScore]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">SpendSignal AI</h1>
            <p className="text-sm text-gray-500">Regulatory Forced-Spend Intelligence</p>
          </div>
          <div className="flex gap-2">
            {['sec_edgar','openfda','sam_gov','epa_echo','usaspending'].map(src => (
              <button
                key={src}
                onClick={() => triggerIngestion(src)}
                disabled={ingesting}
                className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded disabled:opacity-50"
              >
                {ingesting ? '...' : `Ingest ${src.replace('_',' ')}`}
              </button>
            ))}
          </div>
        </div>
      </header>

      {summary && (
        <div className="max-w-7xl mx-auto px-6 py-4 grid grid-cols-4 gap-4">
          <div className="bg-white rounded-lg p-4 border">
            <div className="text-2xl font-bold text-gray-900">{summary.total_leads}</div>
            <div className="text-sm text-gray-500">Total Leads</div>
          </div>
          <div className="bg-white rounded-lg p-4 border">
            <div className="text-2xl font-bold text-red-500">{summary.high_priority_leads}</div>
            <div className="text-sm text-gray-500">High Priority</div>
          </div>
          <div className="bg-white rounded-lg p-4 border">
            <div className="text-2xl font-bold text-indigo-600">{summary.avg_opportunity_score}</div>
            <div className="text-sm text-gray-500">Avg Score</div>
          </div>
          <div className="bg-white rounded-lg p-4 border">
            <div className="text-sm font-medium text-gray-700">By Source</div>
            {Object.entries(summary.by_source).map(([s, c]) => (
              <div key={s} className="text-xs text-gray-500">{s}: {c}</div>
            ))}
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-6 py-2 flex gap-3">
        <input
          type="text" placeholder="Search leads..."
          value={search} onChange={e => setSearch(e.target.value)}
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <select value={source} onChange={e => setSource(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
          <option value="">All Sources</option>
          {['sec_edgar','openfda','sam_gov','epa_echo','usaspending'].map(s => (
            <option key={s} value={s}>{s.replace('_',' ')}</option>
          ))}
        </select>
        <select value={minScore} onChange={e => setMinScore(Number(e.target.value))}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
          <option value={0}>All Scores</option>
          <option value={40}>40+ Medium</option>
          <option value={70}>70+ High</option>
        </select>
      </div>

      <main className="max-w-7xl mx-auto px-6 py-4">
        {loading ? (
          <div className="text-center py-16 text-gray-400">Loading leads...</div>
        ) : leads.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-500 text-lg mb-4">No leads yet.</p>
            <p className="text-gray-400 text-sm">Click an Ingest button above to pull data from sources.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {leads.map(lead => <LeadCard key={lead.id} lead={lead} />)}
          </div>
        )}
      </main>
    </div>
  );
}
