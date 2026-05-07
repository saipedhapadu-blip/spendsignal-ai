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
  if (num >= 70) return <span style={{background:'#ef4444',color:'#fff',fontSize:'11px',fontWeight:700,padding:'2px 8px',borderRadius:'999px'}}>{num}</span>;
  if (num >= 40) return <span style={{background:'#f59e0b',color:'#fff',fontSize:'11px',fontWeight:700,padding:'2px 8px',borderRadius:'999px'}}>{num}</span>;
  return <span style={{background:'#60a5fa',color:'#fff',fontSize:'11px',fontWeight:700,padding:'2px 8px',borderRadius:'999px'}}>{num}</span>;
}

function Tag({ label, type }: { label: string; type: 'trigger' | 'spend' | 'buyer' }) {
  const styles: Record<string, React.CSSProperties> = {
    trigger: {background:'#fee2e2',color:'#b91c1c',fontSize:'11px',padding:'2px 8px',borderRadius:'4px',display:'inline-block',marginRight:'4px',marginBottom:'4px'},
    spend:   {background:'#e0e7ff',color:'#3730a3',fontSize:'11px',padding:'2px 8px',borderRadius:'4px',display:'inline-block',marginRight:'4px',marginBottom:'4px'},
    buyer:   {background:'#dcfce7',color:'#166534',fontSize:'11px',padding:'2px 8px',borderRadius:'4px',display:'inline-block',marginRight:'4px',marginBottom:'4px'},
  };
  return <span style={styles[type]}>{label.replace(/_/g,' ')}</span>;
}

function LeadCard({ lead }: { lead: Lead }) {
  const [open, setOpen] = useState(false);
  const triggers = Array.isArray(lead.trigger_categories) ? lead.trigger_categories : [];
  const spend = Array.isArray(lead.forced_spend_categories) ? lead.forced_spend_categories : [];
  const buyers = Array.isArray(lead.buyer_segments) ? lead.buyer_segments : [];
  const score = Number(lead.opportunity_score) || 0;
  return (
    <div style={{background:'#fff',border:'1px solid #e5e7eb',borderRadius:'12px',padding:'16px',marginBottom:'12px',boxShadow:'0 1px 3px rgba(0,0,0,0.07)'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px'}}>
        <div style={{flex:1,minWidth:0}}>
          <div style={{fontWeight:600,fontSize:'14px',color:'#111827',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{lead.org_name || 'Unknown'}</div>
          <div style={{display:'flex',gap:'8px',marginTop:'4px',alignItems:'center'}}>
            <span style={{background:'#f3f4f6',color:'#4b5563',fontSize:'11px',padding:'2px 8px',borderRadius:'4px'}}>{(lead.source||'').replace(/_/g,' ')}</span>
            {lead.external_id && <span style={{fontSize:'10px',color:'#9ca3af',overflow:'hidden',textOverflow:'ellipsis',maxWidth:'200px'}}>{lead.external_id}</span>}
          </div>
        </div>
        <ScoreBadge score={score} />
      </div>
      {triggers.length > 0 && (
        <div style={{marginTop:'10px'}}>
          <div style={{fontSize:'11px',color:'#6b7280',fontWeight:500,marginBottom:'4px'}}>Triggers</div>
          <div>{triggers.map((t,i) => <Tag key={i} label={t} type="trigger" />)}</div>
        </div>
      )}
      {spend.length > 0 && (
        <div style={{marginTop:'8px'}}>
          <div style={{fontSize:'11px',color:'#6b7280',fontWeight:500,marginBottom:'4px'}}>Spend Categories</div>
          <div>{spend.slice(0,5).map((s,i) => <Tag key={i} label={s} type="spend" />)}</div>
        </div>
      )}
      {lead.why_now && <p style={{marginTop:'8px',fontSize:'12px',color:'#374151'}}><strong>Why now:</strong> {lead.why_now}</p>}
      {lead.sales_angle && <p style={{marginTop:'4px',fontSize:'12px',color:'#374151'}}><strong>Sales angle:</strong> {lead.sales_angle}</p>}
      {open && buyers.length > 0 && (
        <div style={{marginTop:'8px'}}>
          <div style={{fontSize:'11px',color:'#6b7280',fontWeight:500,marginBottom:'4px'}}>Buyer Segments</div>
          <div>{buyers.map((b,i) => <Tag key={i} label={b} type="buyer" />)}</div>
        </div>
      )}
      <button onClick={() => setOpen(!open)} style={{marginTop:'8px',fontSize:'11px',color:'#6366f1',background:'none',border:'none',cursor:'pointer',padding:0}}>
        {open ? 'Show less' : 'Show more'}
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
      const seen = new Map<string, Lead>();
      for (const lead of raw) {
        const key = lead.external_id || lead.id;
        if (!seen.has(key)) seen.set(key, lead);
      }
      setLeads(Array.from(seen.values()));
      setTotal(data.total || 0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [source, page]);

  const fetchSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/leads/summary`);
      if (res.ok) setSummary(await res.json());
    } catch {}
  }, []);

  useEffect(() => { fetchLeads(); fetchSummary(); }, [fetchLeads, fetchSummary]);

  const filtered = leads.filter(l => {
    const q = search.toLowerCase();
    const matchQ = !q || (l.org_name||'').toLowerCase().includes(q) || (l.why_now||'').toLowerCase().includes(q);
    const s = Number(l.opportunity_score)||0;
    const matchS = scoreFilter==='all' ? true : scoreFilter==='high' ? s>=70 : scoreFilter==='medium' ? s>=40&&s<70 : s<40;
    return matchQ && matchS;
  });

  const triggerIngest = async (src: string) => {
    setIngesting(true); setIngestMsg('');
    try {
      const res = await fetch(`${API}/api/ingestion/trigger/${src}`, { method:'POST' });
      const d = await res.json();
      setIngestMsg(d.message || 'Started');
      setTimeout(() => { fetchLeads(); fetchSummary(); }, 8000);
    } catch (e: unknown) {
      setIngestMsg(e instanceof Error ? e.message : 'Error');
    } finally { setIngesting(false); }
  };

  const hdr: React.CSSProperties = {background:'#fff',borderBottom:'1px solid #e5e7eb',padding:'12px 24px',display:'flex',alignItems:'center',justifyContent:'space-between',flexWrap:'wrap',gap:'8px',position:'sticky',top:0,zIndex:10};
  const btn: React.CSSProperties = {fontSize:'12px',background:'#4f46e5',color:'#fff',border:'none',padding:'6px 14px',borderRadius:'6px',cursor:'pointer',opacity:ingesting?0.5:1};
  const card: React.CSSProperties = {background:'#fff',border:'1px solid #e5e7eb',borderRadius:'12px',padding:'16px'};
  const inp: React.CSSProperties = {border:'1px solid #d1d5db',borderRadius:'8px',padding:'8px 12px',fontSize:'13px',flex:1,minWidth:'180px',outline:'none'};
  const sel: React.CSSProperties = {border:'1px solid #d1d5db',borderRadius:'8px',padding:'8px 12px',fontSize:'13px',outline:'none'};
  const pgbtn: React.CSSProperties = {fontSize:'12px',border:'1px solid #d1d5db',padding:'4px 12px',borderRadius:'6px',background:'#fff',cursor:'pointer'};

  return (
    <div style={{minHeight:'100vh',background:'#f9fafb',fontFamily:'system-ui,sans-serif'}}>
      <div style={hdr}>
        <div>
          <div style={{fontWeight:700,fontSize:'18px',color:'#111827'}}>SpendSignal AI</div>
          <div style={{fontSize:'12px',color:'#6b7280'}}>Regulatory Forced-Spend Intelligence</div>
        </div>
        <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
          {['sec_edgar','openfda','sam_gov','epa_echo','usaspending'].map(s => (
            <button key={s} style={btn} disabled={ingesting} onClick={() => triggerIngest(s)}>
              Ingest {s.replace(/_/g,' ')}
            </button>
          ))}
        </div>
      </div>
      {ingestMsg && <div style={{background:'#ecfdf5',color:'#065f46',padding:'8px 24px',fontSize:'12px'}}>{ingestMsg}</div>}

      <div style={{maxWidth:'1200px',margin:'0 auto',padding:'24px 16px'}}>
        {summary && (
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'16px',marginBottom:'24px'}}>
            <div style={card}><div style={{fontSize:'28px',fontWeight:700,color:'#111827'}}>{summary.total_leads.toLocaleString()}</div><div style={{fontSize:'12px',color:'#6b7280',marginTop:'4px'}}>Total Leads</div></div>
            <div style={card}><div style={{fontSize:'28px',fontWeight:700,color:'#dc2626'}}>{summary.high_priority_leads.toLocaleString()}</div><div style={{fontSize:'12px',color:'#6b7280',marginTop:'4px'}}>High Priority</div></div>
            <div style={card}><div style={{fontSize:'28px',fontWeight:700,color:'#111827'}}>{Math.round(summary.avg_opportunity_score)}</div><div style={{fontSize:'12px',color:'#6b7280',marginTop:'4px'}}>Avg Score</div></div>
            <div style={card}><div style={{fontSize:'12px',fontWeight:600,color:'#374151',marginBottom:'6px'}}>By Source</div>{Object.entries(summary.by_source).map(([k,v])=><div key={k} style={{fontSize:'12px',color:'#6b7280'}}>{k.replace(/_/g,' ')}: <strong>{v}</strong></div>)}</div>
          </div>
        )}

        <div style={{display:'flex',gap:'12px',marginBottom:'16px',flexWrap:'wrap'}}>
          <input style={inp} placeholder="Search leads..." value={search} onChange={e=>setSearch(e.target.value)} />
          <select style={sel} value={source} onChange={e=>{setSource(e.target.value);setPage(0);}}>
            <option value="all">All Sources</option>
            <option value="sec_edgar">SEC Edgar</option>
            <option value="openfda">OpenFDA</option>
            <option value="sam_gov">SAM.gov</option>
            <option value="epa_echo">EPA Echo</option>
            <option value="usaspending">USAspending</option>
          </select>
          <select style={sel} value={scoreFilter} onChange={e=>setScoreFilter(e.target.value)}>
            <option value="all">All Scores</option>
            <option value="high">High (70+)</option>
            <option value="medium">Medium (40-69)</option>
            <option value="low">Low (&lt;40)</option>
          </select>
        </div>

        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'12px'}}>
          <span style={{fontSize:'13px',color:'#6b7280'}}>Showing <strong>{filtered.length}</strong> of <strong>{total.toLocaleString()}</strong> leads</span>
          <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
            <button style={pgbtn} disabled={page===0} onClick={()=>setPage(p=>Math.max(0,p-1))}>Prev</button>
            <span style={{fontSize:'12px',color:'#374151'}}>Page {page+1}</span>
            <button style={pgbtn} disabled={(page+1)*LIMIT>=total} onClick={()=>setPage(p=>p+1)}>Next</button>
          </div>
        </div>

        {loading && <div style={{textAlign:'center',padding:'48px',color:'#6b7280'}}>Loading leads...</div>}
        {error && <div style={{textAlign:'center',padding:'24px',color:'#dc2626'}}>{error}</div>}
        {!loading && !error && filtered.length===0 && <div style={{textAlign:'center',padding:'48px',color:'#9ca3af'}}>No leads found.</div>}
        <div style={{columns:'1',gap:'12px'}}>
          {filtered.map(lead => <LeadCard key={lead.id} lead={lead} />)}
        </div>
      </div>
    </div>
  );
}
