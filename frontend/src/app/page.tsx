'use client';
import { useState, useEffect, useCallback } from 'react';

const API = 'https://spendsignal-ai-production.up.railway.app';

interface Lead {
  id: string;
  org_name: string;
  source: string;
  trigger_categories: string[];
  forced_spend_categories: string[];
  opportunity_score: number;
  severity: string | number;
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
  const num = Number(score) || 0;
  const color = num >= 70 ? 'bg-red-500' : num >= 40 ? 'bg-yellow-500' : 'bg-blue-400';
  return (
    <span className={`inline-block ${color} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>
      {num}
    </span>
  );
}

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-block ${color} text-xs px-2 py-0.5 rounded mr-1 mb-1`}>
      {label.replace(/_/g, ' ')}
    </span>
  );
}

function LeadCard({ lead }: { lead: Lead }) {
  const [expanded, setExpanded] = useState(false);
  const triggers = Array.isArray(lead.trigger_categories) ? lead.trigger_categories : [];
  const spend = Array.isArray(lead.forced_spend_categories) ? lead.forced_spend_categories : [];
  const buyers = Array.isArray(lead.buyer_segments) ? lead.buyer_segments : [];
  const score = Number(lead.opportunity_score) || 0;
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow mb-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 text-sm truncate">{lead.org_name || 'Unknown'}</h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
              {(lead.source || '').replace(/_/g, ' ')}
            </span>
            {lead.external_id && (
              <span className="text-xs text-gray-400 truncate max-w-xs">{lead.external_id}</span>
            )}
          </div>
        </div>
        <ScoreBadge score={score} />
      </div>
      {triggers.length > 0 && (
        <div className="mt-2">
          <p className="text-xs text-gray-500 font-medium mb-1">Triggers</p>
          <div className="flex flex-wrap">
            {triggers.map((t, i) => <Chip key={i} label={t} color="bg-red-100 text-red-700" />)}
          </div>
        </div>
      )}
      {spend.slice(0, 3).length > 0 && (
        <div className="mt-1">
          <p className="text-xs text-gray-500 font-medium mb-1">Spend Categories</p>
          <div className="flex flex-wrap">
            {spend.slice(0, 5).map((s, i) => <Chip key={i} label={s} color="bg-indigo-100 text-indigo-700" />)}
          </div>
        </div>
      )}
      {lead.why_now && (
        <p className="mt-2 text-xs text-gray-600"><span className="font-medium">Why now:</span> {lead.why_now}</p>
      )}
      {lead.sales_angle && (
        <p className="mt-1 text-xs text-gray-600"><span className="font-medium">Sales angle:</span> {lead.sales_angle}</p>
      )}
      {buyers.length > 0 && expanded && (
        <div className="mt-2">
          <p className="text-xs text-gray-500 font-medium mb-1">Buyer Segments</p>
          <div className="flex flex-wrap">
            {buyers.map((b, i) => <Chip key={i} label={b} color="bg-green-100 text-green-700" />)}
          </div>
        </div>
      )}
      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-2 text-xs text-blue-500 hover:text-blue-700"
      >
        {expanded ? 'Show less' : 'Show more'}
      </button>
    </div>
  );
}

export default function Home() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [search, setSearch] = useState('');
  const [source, setSource] = useState('all');
  const [scoreFilter, setScoreFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [ingesting, setIngesting] = useState(false);
  const [ingestMsg, setIngestMsg] = useState('');
  const LIMIT = 50;

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const src = source !== 'all' ? `&source=${source}` : '';
      const res = await fetch(`${API}/api/leads/?limit=${LIMIT}&offset=${page * LIMIT}${src}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const raw: Lead[] = data.leads || [];
      // Deduplicate by external_id (prefer last seen) or by id
      const seen = new Map<string, Lead>();
      for (const lead of raw) {
        const key = lead.external_id || lead.id;
        if (!seen.has(key)) seen.set(key, lead);
      }
      setLeads(Array.from(seen.values()));
      setTotal(data.total || 0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to fetch leads');
    } finally {
      setLoading(false);
    }
  }, [source, page]);

  const fetchSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/leads/summary`);
      if (!res.ok) return;
      setSummary(await res.json());
    } catch {}
  }, []);

  useEffect(() => { fetchLeads(); fetchSummary(); }, [fetchLeads, fetchSummary]);

  const filtered = leads.filter(l => {
    const q = search.toLowerCase();
    const matchSearch = !q ||
      (l.org_name || '').toLowerCase().includes(q) ||
      (l.why_now || '').toLowerCase().includes(q) ||
      (l.sales_angle || '').toLowerCase().includes(q);
    const score = Number(l.opportunity_score) || 0;
    const matchScore =
      scoreFilter === 'all' ? true :
      scoreFilter === 'high' ? score >= 70 :
      scoreFilter === 'medium' ? score >= 40 && score < 70 :
      score < 40;
    return matchSearch && matchScore;
  });

  const triggerIngest = async (src: string) => {
    setIngesting(true);
    setIngestMsg('');
    try {
      const res = await fetch(`${API}/api/ingestion/trigger/${src}`, { method: 'POST' });
      const data = await res.json();
      setIngestMsg(data.message || JSON.stringify(data));
      setTimeout(() => { fetchLeads(); fetchSummary(); }, 5000);
    } catch (e: unknown) {
      setIngestMsg(e instanceof Error ? e.message : 'Error');
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">SpendSignal AI</h1>
            <p className="text-xs text-gray-500">Regulatory Forced-Spend Intelligence</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            {['sec edgar', 'openfda', 'sam gov', 'epa echo', 'usaspending'].map((s, i) => {
              const src = ['sec_edgar','openfda','sam_gov','epa_echo','usaspending'][i];
              return (
                <button
                  key={src}
                  onClick={() => triggerIngest(src)}
                  disabled={ingesting}
                  className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1 rounded disabled:opacity-50"
                >
                  Ingest {s}
                </button>
              );
            })}
          </div>
        </div>
        {ingestMsg && (
          <div className="max-w-7xl mx-auto px-4 pb-2 text-xs text-green-700">{ingestMsg}</div>
        )}
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-2xl font-bold text-gray-900">{summary.total_leads.toLocaleString()}</p>
              <p className="text-xs text-gray-500 mt-1">Total Leads</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-2xl font-bold text-red-600">{summary.high_priority_leads.toLocaleString()}</p>
              <p className="text-xs text-gray-500 mt-1">High Priority</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-2xl font-bold text-gray-900">{Math.round(summary.avg_opportunity_score)}</p>
              <p className="text-xs text-gray-500 mt-1">Avg Score</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs font-medium text-gray-700 mb-1">By Source</p>
              {Object.entries(summary.by_source).map(([k, v]) => (
                <p key={k} className="text-xs text-gray-600">{k.replace(/_/g, ' ')}: <span className="font-semibold">{v}</span></p>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-3 mb-4">
          <input
            type="text"
            placeholder="Search leads..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1 min-w-48 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
          <select
            value={source}
            onChange={e => { setSource(e.target.value); setPage(0); }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            <option value="all">All Sources</option>
            <option value="sec_edgar">SEC Edgar</option>
            <option value="openfda">OpenFDA</option>
            <option value="sam_gov">SAM.gov</option>
            <option value="epa_echo">EPA Echo</option>
            <option value="usaspending">USAspending</option>
          </select>
          <select
            value={scoreFilter}
            onChange={e => setScoreFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            <option value="all">All Scores</option>
            <option value="high">High (70+)</option>
            <option value="medium">Medium (40-69)</option>
            <option value="low">Low (&lt;40)</option>
          </select>
        </div>

        <div className="flex items-center justify-between mb-3">
          <p className="text-sm text-gray-600">
            Showing <span className="font-semibold">{filtered.length}</span> of <span className="font-semibold">{total.toLocaleString()}</span> leads
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="text-xs px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
            >Prev</button>
            <span className="text-xs py-1 px-2">Page {page + 1}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={(page + 1) * LIMIT >= total}
              className="text-xs px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
            >Next</button>
          </div>
        </div>

        {loading && <p className="text-center text-gray-500 py-12">Loading leads...</p>}
        {error && <p className="text-center text-red-500 py-6">{error}</p>}
        {!loading && !error && filtered.length === 0 && (
          <p className="text-center text-gray-400 py-12">No leads found. Try ingesting data above.</p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-0">
          {filtered.map(lead => <LeadCard key={lead.id} lead={lead} />)}
        </div>
      </main>
    </div>
  );
}
