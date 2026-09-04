import { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, Legend, ResponsiveContainer, Cell
} from 'recharts';
import { ShieldAlert, IndianRupee, Activity, Play, CheckCircle2, AlertTriangle, Info, X } from 'lucide-react';
import './index.css';

const API_BASE = 'http://localhost:8000/api';

export default function App() {
  const [metrics, setMetrics] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  const [failureCases, setFailureCases] = useState([]);
  const [mandateStats, setMandateStats] = useState(null);
  const [decisionTable, setDecisionTable] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  const fetchData = async () => {
    try {
      const [metricsRes, auditRes, failRes, mandRes, tableRes] = await Promise.all([
        fetch(`${API_BASE}/metrics`),
        fetch(`${API_BASE}/audit-trail?limit=100`),
        fetch(`${API_BASE}/failure-cases`),
        fetch(`${API_BASE}/mandate-stats`),
        fetch(`${API_BASE}/decision-table`),
      ]);
      setMetrics(await metricsRes.json());
      const auditData = await auditRes.json();
      setAuditLog(auditData.records);
      setFailureCases(await failRes.json());
      setMandateStats(await mandRes.json());
      setDecisionTable(await tableRes.json());
    } catch (err) {
      console.error("Failed to fetch data", err);
    }
  };

  const runBatch = async () => {
    setIsLoading(true);
    try {
      await fetch(`${API_BASE}/run-batch`);
      await fetchData();
    } catch (err) {
      console.error("Batch run failed", err);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, []);

  const formatCurrency = (val) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
  const formatCompact = (val) => new Intl.NumberFormat('en-IN', { notation: 'compact' }).format(val);

  if (!metrics) {
    return (
      <div className="empty-state" style={{ height: '100vh' }}>
        <ShieldAlert className="empty-state-icon loading-pulse" />
        <h2 style={{ color: 'white', marginBottom: '8px' }}>Orchestrator Initializing</h2>
        <p className="empty-state-text">Waiting for backend connection...</p>
        <button className="run-batch-btn" style={{ marginTop: '24px' }} onClick={runBatch} disabled={isLoading}>
          {isLoading ? <span className="spinner"></span> : <span>Run Synthetic Batch</span>}
        </button>
      </div>
    );
  }

  // Chart data prep
  const chartData = Object.entries(metrics.by_source || {}).map(([key, val]) => ({
    name: key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
    AtRisk: val.at_risk,
    Recovered: val.recovered
  }));

  const COLORS = ['#3395FF', '#10B981', '#F59E0B', '#8B5CF6'];

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Unified Revenue Recovery Orchestrator</h1>
          <div className="subtitle">AI-driven intervention for payment declines, checkout abandons, and overdue receivables.</div>
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <button className="filter-btn" onClick={() => setIsPanelOpen(true)}>
            <Info size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'text-bottom' }} />
            View Decision Rules
          </button>
          <button className="run-batch-btn" onClick={runBatch} disabled={isLoading}>
            {isLoading ? <span className="spinner"></span> : <><Play size={16} fill="currentColor" /> Run New Batch</>}
          </button>
        </div>
      </header>

      {/* METRICS ROW */}
      <div className="metrics-bar animate-fade-in" style={{ marginBottom: '32px' }}>
        <div className="glass-card metric-card risk">
          <div className="metric-icon"><AlertTriangle size={20} /></div>
          <div className="metric-value">{formatCompact(metrics.total_at_risk)}</div>
          <div className="metric-label">Total ₹ At Risk</div>
        </div>
        <div className="glass-card metric-card recovered">
          <div className="metric-icon"><IndianRupee size={20} /></div>
          <div className="metric-value">{formatCompact(metrics.total_recovered)}</div>
          <div className="metric-label">Total ₹ Recovered</div>
        </div>
        <div className="glass-card metric-card rate">
          <div className="metric-icon"><Activity size={20} /></div>
          <div className="metric-value">{metrics.recovery_rate}%</div>
          <div className="metric-label">Overall Recovery Rate</div>
        </div>
        <div className="glass-card metric-card count">
          <div className="metric-icon"><ShieldAlert size={20} /></div>
          <div className="metric-value">{metrics.actions_taken}</div>
          <div className="metric-label">Interventions Triggered</div>
        </div>
      </div>

      <div className="dashboard-grid">
        
        {/* MANDATE PANEL */}
        {mandateStats && (
          <div className="glass-card full-width animate-slide-up">
            <div className="card-header">
              <h2 className="card-title">UPI Autopay Mandate Budget Tracker</h2>
              <div className="badge badge-blue">Specialized Risk Type</div>
            </div>
            
            <div className="mandate-stats-grid">
              <div className="mandate-stat">
                <div className="mandate-stat-value">{mandateStats.at_risk_mandates} / {mandateStats.total_mandates}</div>
                <div className="mandate-stat-label">Mandates with ≤1 Retry Left</div>
              </div>
              <div className="mandate-stat">
                <div className="mandate-stat-value" style={{color: 'var(--accent-amber)'}}>{mandateStats.optimal_window_holds}</div>
                <div className="mandate-stat-label">Holds for Optimal Window</div>
              </div>
              <div className="mandate-stat">
                <div className="mandate-stat-value" style={{color: 'var(--accent-red)'}}>{mandateStats.budget_exhausted}</div>
                <div className="mandate-stat-label">Budget Exhausted (Escalated)</div>
              </div>
            </div>

            <div className="mandate-highlight">
              <div className="mandate-highlight-title">
                <CheckCircle2 size={16} /> Edge Case Protection Active
              </div>
              <div className="mandate-highlight-body">
                The orchestrator treats NPCI retries as a scarce resource. It held <b>{mandateStats.optimal_window_holds}</b> last-chance retries for statistically derived optimal windows, escalated <b>{mandateStats.budget_exhausted}</b> fully exhausted mandates to human review, and detected <b>{mandateStats.cycle_deadline_escalations}</b> cases where the billing cycle ends before the optimal window arrives.
              </div>
            </div>
          </div>
        )}

        {/* CHART */}
        <div className="glass-card animate-slide-up" style={{ animationDelay: '100ms' }}>
          <div className="card-header">
            <h2 className="card-title">Recovery by Risk Category</h2>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{fontSize: 10}} interval={0} tickFormatter={(val) => val.replace(' ', '\n')} />
                <YAxis tickFormatter={(val) => formatCompact(val)} />
                <RechartsTooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} wrapperClassName="custom-tooltip" formatter={(val) => formatCurrency(val)} />
                <Legend iconType="circle" />
                <Bar dataKey="AtRisk" name="₹ At Risk" fill="var(--bg-tertiary)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Recovered" name="₹ Recovered" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* FAILURE CASES (STOPPING RULES) */}
        <div className="glass-card animate-slide-up" style={{ animationDelay: '200ms', overflowY: 'auto', maxHeight: '400px' }}>
          <div className="card-header" style={{position: 'sticky', top: '-24px', background: 'var(--glass-bg)', zIndex: 5, padding: '24px 0 16px', margin: '-24px 0 16px', backdropFilter: 'blur(16px)'}}>
            <div>
              <h2 className="card-title">Graceful Failures & Guardrails</h2>
              <div className="card-subtitle">Showcasing stopping rules doing their job</div>
            </div>
            <div className="badge badge-amber badge-outline">{failureCases.length} Cases</div>
          </div>
          
          <div style={{display: 'flex', flexDirection: 'column', gap: '16px'}}>
            {failureCases.slice(0, 15).map((fail, i) => (
              <div key={i} className="failure-card">
                <div className="failure-card-header">
                  <AlertTriangle size={16} />
                  <span className="failure-card-title">{fail.stopping_rule}</span>
                </div>
                <div className="failure-card-body">
                  "{fail.reasoning}"
                </div>
                <dl className="failure-card-detail">
                  <dt>Risk ID:</dt><dd>{fail.risk_id}</dd>
                  <dt>Customer:</dt><dd>{fail.customer_id}</dd>
                </dl>
              </div>
            ))}
            {failureCases.length === 0 && (
              <div style={{color: 'var(--text-muted)', textAlign: 'center', padding: '32px 0'}}>
                No guardrail activations in this batch.
              </div>
            )}
          </div>
        </div>

        {/* FULL AUDIT TRAIL */}
        <div className="glass-card full-width animate-slide-up" style={{ animationDelay: '300ms' }}>
          <div className="card-header">
            <h2 className="card-title">Live Execution Audit Trail</h2>
            <div className="badge badge-outline">Latest 100 entries</div>
          </div>
          <div className="audit-trail-wrapper">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Risk Type</th>
                  <th>Action</th>
                  <th>Outcome</th>
                  <th>₹ Recovered</th>
                  <th>Decision Reasoning</th>
                </tr>
              </thead>
              <tbody>
                {auditLog.map((log, i) => (
                  <tr key={i} className={log.is_mandate ? 'row-mandate' : `row-${log.outcome}`}>
                    <td>{new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}</td>
                    <td>
                      <div style={{display: 'flex', alignItems: 'center', gap: '6px'}}>
                        {log.is_mandate && <span className="badge badge-blue">Mandate</span>}
                        {log.risk_type.replace('_', ' ')}
                      </div>
                    </td>
                    <td>{log.action.replace(/_/g, ' ')}</td>
                    <td>
                      <span className={`badge badge-${
                        log.outcome === 'paid' ? 'green' :
                        log.outcome === 'responded' ? 'green' :
                        log.outcome === 'no_response' ? 'red' :
                        log.outcome === 'failed' ? 'red' : 'amber'
                      }`}>
                        {log.outcome}
                      </span>
                    </td>
                    <td style={{fontWeight: 600}}>{log.amount_recovered > 0 ? formatCurrency(log.amount_recovered) : '-'}</td>
                    <td style={{maxWidth: '250px', whiteSpace: 'normal', fontSize: '0.75rem', lineHeight: 1.4}}>
                      {log.reasoning}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* DECISION TABLE PANEL */}
      <div className={`decision-panel-overlay ${isPanelOpen ? 'open' : ''}`} onClick={() => setIsPanelOpen(false)}></div>
      <div className={`decision-panel ${isPanelOpen ? 'open' : ''}`}>
        <button className="panel-close" onClick={() => setIsPanelOpen(false)}><X size={18} /></button>
        <h2 style={{fontSize: '1.2rem', fontWeight: 600, marginBottom: '24px', color: 'var(--text-primary)'}}>
          Decision Engine Rules
        </h2>
        
        {decisionTable && (
          <>
            <div style={{marginBottom: '32px'}}>
              <h3 style={{fontSize: '0.9rem', color: 'var(--accent-red)', marginBottom: '12px'}}>Priority Stopping Rules (Checked First)</h3>
              <table className="rule-table">
                <thead><tr><th>Rule</th><th>Behavior</th></tr></thead>
                <tbody>
                  {decisionTable.stopping_rules.sort((a,b)=>a.priority-b.priority).map((r, i) => (
                    <tr key={i}>
                      <td style={{color: 'white', fontWeight: 500}}>{r.name}</td>
                      <td>{r.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{marginBottom: '32px'}}>
              <h3 style={{fontSize: '0.9rem', color: 'var(--accent-blue)', marginBottom: '12px'}}>Mandate-Aware Branch</h3>
              <table className="rule-table">
                <thead><tr><th>Condition</th><th>Action</th></tr></thead>
                <tbody>
                  {decisionTable.mandate_rules.map((r, i) => (
                    <tr key={i}>
                      <td style={{color: 'white'}}>{r.condition}</td>
                      <td style={{color: 'var(--accent-blue)'}}>{r.action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div>
              <h3 style={{fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '12px'}}>Standard Matrix</h3>
              <table className="rule-table">
                <thead><tr><th>Risk Type</th><th>Cause</th><th>Action</th></tr></thead>
                <tbody>
                  {decisionTable.standard_rules.map((r, i) => (
                    <tr key={i}>
                      <td style={{whiteSpace: 'nowrap'}}>{r.risk_type}</td>
                      <td style={{color: 'white'}}>{r.cause}</td>
                      <td>{r.action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
