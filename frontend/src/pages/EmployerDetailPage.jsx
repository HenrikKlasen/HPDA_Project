import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';

function EmployerDetailPage() {
  const { id } = useParams();
  const [summary, setSummary] = useState(null);
  const [transitions, setTransitions] = useState(null);

  useEffect(() => {
    fetch('/api/employer_summary')
      .then(res => res.json())
      .then(d => setSummary(Array.isArray(d) ? d.find(e => String(e.employerId) === String(id) || String(e.id) === String(id)) : null))
      .catch(() => setSummary(null));

    fetch('/api/job_transitions')
      .then(res => res.json())
      .then(d => setTransitions(d))
      .catch(() => setTransitions(null));
  }, [id]);

  const fmtCurrency = (v) => {
    if (v === undefined || v === null || Number.isNaN(Number(v))) return '—';
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(Number(v));
  };

  return (
    <section>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
        <h2>Employer Profile — {id}</h2>
        <Link to="/map" style={{ marginLeft: 'auto' }}>← Back to map</Link>
      </div>

      {!summary && <p>No summary data available for this employer.</p>}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div style={{ background: '#fff', padding: 12, borderRadius: 8 }}>
            <h3>Overview</h3>
            <div><strong>Name:</strong> {summary.name ?? summary.employerName ?? '—'}</div>
            <div><strong>ID:</strong> {summary.employerId ?? summary.id}</div>
            <div><strong>Sector:</strong> {summary.Sector ?? summary.sector ?? '—'}</div>
            <div><strong>Job count:</strong> {summary.JobCount ?? summary.job_count ?? '—'}</div>
            <div><strong>Avg hourly rate:</strong> {summary.AverageHourlyRate ? `$${summary.AverageHourlyRate}` : (summary.avg_rate ? `$${summary.avg_rate}` : '—')}</div>
          </div>
          <div style={{ background: '#fff', padding: 12, borderRadius: 8 }}>
            <h3>Financials (estimates)</h3>
            <div><strong>Estimated annual revenue:</strong> {fmtCurrency(((summary.JobCount ?? summary.job_count) || 0) * ((summary.AverageHourlyRate ?? summary.avg_rate) || 0) * 40 * 52)}</div>
            <div><strong>Estimated payroll:</strong> {fmtCurrency(((summary.JobCount ?? summary.job_count) || 0) * ((summary.AverageHourlyRate ?? summary.avg_rate) || 0) * 40 * 52 * 0.6)}</div>
            <div><strong>Estimated profit (quick est):</strong> {fmtCurrency((((summary.JobCount ?? summary.job_count) || 0) * ((summary.AverageHourlyRate ?? summary.avg_rate) || 0) * 40 * 52) * 0.1)}</div>
          </div>
          <div style={{ gridColumn: '1 / -1', background: '#fff', padding: 12, borderRadius: 8 }}>
            <h3>Transfers (top)</h3>
            {transitions && transitions.nodes && transitions.links ? (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr><th>Employer</th><th style={{ textAlign: 'center' }}>In</th><th style={{ textAlign: 'center' }}>Out</th></tr>
                </thead>
                <tbody>
                  {transitions.nodes.slice(0, 12).map((n, i) => {
                    const incoming = transitions.links.find(l => Number(l.target) === Number(id) && Number(l.source) === Number(n.id));
                    const outgoing = transitions.links.find(l => Number(l.source) === Number(id) && Number(l.target) === Number(n.id));
                    const total = (incoming?.value || 0) + (outgoing?.value || 0);
                    if (!total) return null;
                    return (
                      <tr key={i}><td>{n.name}</td><td style={{ textAlign: 'center' }}>{incoming?.value ?? '—'}</td><td style={{ textAlign: 'center' }}>{outgoing?.value ?? '—'}</td></tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (<p>No transition data available.</p>)}
          </div>
        </div>
      )}
    </section>
  );
}

export default EmployerDetailPage;
