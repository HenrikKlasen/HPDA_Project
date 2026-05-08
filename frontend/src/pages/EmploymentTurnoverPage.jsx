import { useBackendPage } from '../hooks/useBackendPage';

function EmploymentTurnoverPage() {
  const { html, loading, error, refresh } = useBackendPage(
    'employmentContent',
    '/api/employment-page'
  );

  return (
    <section>
      <div className="section-intro">
        <h2>Employment &amp; Turnover</h2>
        <p>
          Employer stability, worker movement, job turnover, and changes in labor participation over time.
        </p>
      </div>
      <PageFrame html={html} loading={loading} error={error} onRefresh={refresh} />
    </section>
  );
}

function PageFrame({ html, loading, error, onRefresh }) {
  if (loading) return <LoadingState />;
  if (error)   return <ErrorState message={error} onRefresh={onRefresh} />;
  if (!html)   return null;
  return (
    <>
      <RefreshButton onClick={onRefresh} />
      <iframe srcDoc={html} style={{ width: '100%', height: '2200px', border: 'none' }} />
    </>
  );
}

function LoadingState() {
  return (
    <div style={{ padding: '60px 0', textAlign: 'center', color: '#555' }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
      <p style={{ fontSize: 15 }}>Generating visualisation — this may take a moment…</p>
      <p style={{ fontSize: 12, color: '#999', marginTop: 6 }}>
        The backend is querying the database and building the charts.
      </p>
    </div>
  );
}

function ErrorState({ message, onRefresh }) {
  return (
    <div style={{ padding: '40px 20px', textAlign: 'center', color: '#c00' }}>
      <p style={{ fontWeight: 'bold', marginBottom: 8 }}>Failed to load page</p>
      <p style={{ fontSize: 13, color: '#555', marginBottom: 16 }}>{message}</p>
      <button onClick={onRefresh} style={btnStyle}>Retry</button>
    </div>
  );
}

function RefreshButton({ onClick }) {
  return (
    <div style={{ textAlign: 'right', marginBottom: 6 }}>
      <button onClick={onClick} style={btnStyle} title="Clear cache and reload from backend">
        ↺ Refresh
      </button>
    </div>
  );
}

const btnStyle = {
  background: '#2f5d8c', color: '#fff', border: 'none', borderRadius: 6,
  padding: '5px 14px', fontSize: 12, cursor: 'pointer',
};

export default EmploymentTurnoverPage;
