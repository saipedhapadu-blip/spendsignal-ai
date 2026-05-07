'use client';

import { useState, useEffect } from 'react';

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

const SOURCES = ['sec_edgar', 'openfda', 'sam_gov', 'epa_echo', 'usaspending'];

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 70 ? 'bg-red-500' : score >= 40 ? 'bg-yellow-500' : 'bg-blue-400';
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
          <span className="text-xs text-gray-500 uppercase tracking-wide">
            {(lead.source || '').replace(/_/g, ' ')}
          </span>
        </div>
        <ScoreBadge score={lead.opportunity_score} />
      </div>
      <div className="mb-3">
        <div className="flex flex-wrap gap-1 mb-2">
          {(lead.trigger_categories || []).map((cat) => (
            <span
              key={cat}
              className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded"
            >
              {cat.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-1">
          {(lead.forced_spend_categories || []).slice(0, 3).map((cat) => (
            <span
              key={cat}
              className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded"
            >
              {cat.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      </div>
      {lead.why_now && (
        <p className="text-sm text-gray-700 mb-1">
          <span className="font-medium">Why now:</span> {lead.why_now}
        </p>
      )}
      {lead.sales_angle && (
        <p className="text-sm text-gray-600">
          <span className="font-medium">Sales angle:</span> {lead.sales_angle}
        </p>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [search, setSearch] = useState('');
  const [source, setSource] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getApi = () =>
    process.env.NEXT_PUBLIC_API_URL || 'https://spendsignal-ai-production.up.railway.app';

  useEffect(() => {
    setMounted(true);
  }, []);

  const fetchLeads = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (minScore > 0) params.set('min_score', String(minScore));
      if (source) params.set('source', source);
      const url = search
        ? `${getApi()}/search/leads?q=${encodeURIComponent(search)}&${params}`
        : `${getApi()}/leads/?${params}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLeads(data.results || data || []);
    } catch (e) {
      console.error('fetchLeads error:', e);
      setError('Could not load leads. The backend may still be warming up.');
      setLeads([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const res = await fetch(`${getApi()}/leads/stats/summary`);
      if (!res.ok) return;
      const data = await res.json();
      setSummary(data);
    } catch (e) {
      console.error('fetchSummary error:', e);
    }
  };

  const triggerIngestion = async (src: string) => {
    setIngesting(true);
    try {
      await fetch(`${getApi()}/ingestion/run/${src}`, { method: 'POST' });
      setTimeout(() => {
        fetchLeads();
        fetchSummary();
        setIngesting(false);
      }, 3000);
    } catch (e) {
      console.error('ingestion error:', e);
      setIngesting(false);
    }
  };

  useEffect(() => {
    if (!mounted) return;
    fetchLeads();
    fetchSummary();
  }, [mounted, search, source, minScore]);

  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500">Loading SpendSignal AI...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">SpendSignal AI</h1>
            <p className="text-sm text-gray-500">Regulatory Forced-Spend Intelligence</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {SOURCES.map((src) => (
              <button
                key={src}
                onClick={() => triggerIngestion(src)}
                disabled={ingesting}
                className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded disabled:opacity-50 transition-colors"
              >
                {ingesting ? '...' : `Ingest ${src.replace(/_/g, ' ')}`}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
              <p className="text-3xl font-bold text-indigo-600">{summary.total_leads}</p>
              <p className="text-xs text-gray-500 mt-1">Total Leads</p>
            </div>
            <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
              <p className="text-3xl font-bold text-red-500">{summary.high_priority_leads}</p>
              <p className="text-xs text-gray-500 mt-1">High Priority</p>
            </div>
            <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
              <p className="text-3xl font-bold text-yellow-500">
                {Math.round(summary.avg_opportunity_score)}
              </p>
              <p className="text-xs text-gray-500 mt-1">Avg Score</p>
            </div>
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <p className="text-xs font-medium text-gray-700 mb-2">By Source</p>
              {Object.entries(summary.by_source).map(([s, c]) => (
                <p key={s} className="text-xs text-gray-600">
                  {s.replace(/_/g, ' ')}: <span className="font-medium">{c}</span>
                </p>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-3 mb-6">
          <input
            type="text"
            placeholder="Search leads..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 min-w-48 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">All Sources</option>
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value={0}>All Scores</option>
            <option value={40}>40+ Medium</option>
            <option value={70}>70+ High</option>
          </select>
        </div>

        {error && (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg mb-6 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <p className="text-gray-500">Loading leads...</p>
          </div>
        ) : leads.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-600 font-medium">No leads yet.</p>
            <p className="text-gray-400 text-sm mt-2">
              Click an Ingest button above to pull data from sources.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {leads.map((lead) => (
              <LeadCard key={lead.id} lead={lead} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
