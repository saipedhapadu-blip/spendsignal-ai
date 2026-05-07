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
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-gray-900 text-base">{lead.org_name}</h3>
        <ScoreBadge score={lead.opportunity_score} />
      </div>
      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded mr-1">
        {(lead.source || '').replace(/_/g, ' ')}
      </span>
      <div className="mt-2 flex flex-wrap gap-1">
        {(lead.trigger_categories || []).map((cat) => (
          <span key={cat} className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">
            {cat.replace(/_/g, ' ')}
          </span>
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-1">
        {(lead.forced_spend_categories || []).slice(0, 3).map((cat) => (
          <span key={cat} className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded">
            {cat.replace(/_/g, ' ')}
          </span>
        ))}
      </div>
      {lead.why_now && (
        <p className="mt-2 text-xs text-gray-600">
          <span className="font-medium">Why now: </span>{lead.why_now}
        </p>
      )}
      {lead.sales_angle && (
        <p className="mt-1 text-xs text-gray-500">
          <span className="font-medium">Sales angle: </span>{lead.sales_angle}
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

  const getApi = () => process.env.NEXT_PUBLIC_API_URL || 'https://spendsignal-ai-production.up.railway.app';

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
        ? `${getApi()}/api/search/leads?q=${encodeURIComponent(search)}&${params}`
        : `${getApi()}/api/leads/?${params}`;
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
      const res = await fetch(`${getApi()}/api/leads/stats/summary`);
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
      await fetch(`${getApi()}/api/ingestion/run/${src}`, { method: 'POST' });
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
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading SpendSignal AI...</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">SpendSignal AI</h1>
          <p className="text-gray-500 mt-1">Regulatory Forced-Spend Intelligence</p>
        </div>

        <div className="flex flex-wrap gap-2 mb-6">
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

        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <p className="text-2xl font-bold text-gray-900">{summary.total_leads}</p>
              <p className="text-xs text-gray-500 mt-1">Total Leads</p>
            </div>
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <p className="text-2xl font-bold text-red-600">{summary.high_priority_leads}</p>
              <p className="text-xs text-gray-500 mt-1">High Priority</p>
            </div>
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <p className="text-2xl font-bold text-indigo-600">{Math.round(summary.avg_opportunity_score)}</p>
              <p className="text-xs text-gray-500 mt-1">Avg Score</p>
            </div>
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <p className="text-xs font-semibold text-gray-700 mb-1">By Source</p>
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
              <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
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
          <p className="text-amber-600 text-sm mb-4">{error}</p>
        )}
        {loading ? (
          <p className="text-gray-400 text-sm">Loading leads...</p>
        ) : leads.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-400 text-lg">No leads yet.</p>
            <p className="text-gray-400 text-sm mt-1">Click an Ingest button above to pull data from sources.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {leads.map((lead) => (
              <LeadCard key={lead.id} lead={lead} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
