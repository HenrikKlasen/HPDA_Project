import React, { useEffect, useState } from 'react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorState from '../components/common/ErrorState';
import AutoResizingIframe from '../components/common/AutoResizingIframe';
import BuildingsMap from '../components/maps/BuildingsMap';

function EmploymentTurnoverPage() {
  const [iframeContent, setIframeContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('trends'); // 'trends' or 'network'
  
  // Transition Map states
  const [mapData, setMapData] = useState(null);
  const [selectedEmployer, setSelectedEmployer] = useState(null);
  const [employers, setEmployers] = useState([]);
  const [colorblindMode, setColorblindMode] = useState(false);
  
  const inColor = colorblindMode ? '#0ea5e9' : '#22c55e';
  const outColor = colorblindMode ? '#f97316' : '#ef4444';

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // 1. Fetch Trends (Iframe)
      const cachedContent = localStorage.getItem('employmentContent');
      if (cachedContent) {
        setIframeContent(cachedContent);
      } else {
        const res = await fetch('http://localhost:5000/api/employment-page');
        if (!res.ok) throw new Error(`Trends API error: ${res.status}`);
        const html = await res.text();
        localStorage.setItem('employmentContent', html);
        setIframeContent(html);
      }

      // 2. Fetch Network Data (JSON)
      const networkRes = await fetch('http://localhost:5000/api/job_transitions');
      if (!networkRes.ok) throw new Error(`Network API error: ${networkRes.status}`);
      const nData = await networkRes.json();
      setMapData(nData);

      // 3. Load employers from localStorage
      const empData = localStorage.getItem('employers');
      if (empData) {
        const parsed = JSON.parse(empData);
        if (Array.isArray(parsed)) setEmployers(parsed);
      }

      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch employment data:', err);
      setError(err.message);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleEmployerSelect = (pointData) => {
    if (pointData && mapData) {
      const selectedNode = mapData.nodes.find(n => String(n.id) === String(pointData.id));
      if (selectedNode) {
        setSelectedEmployer({
          id: selectedNode.id,
          name: selectedNode.name,
          x: selectedNode.x,
          y: selectedNode.y
        });
      }
    }
  };

  return (
    <section>
      <div className="section-intro" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Labor Dynamics & Workforce Pulse</h2>
          <p>
            {viewMode === 'trends' 
              ? 'City-wide trends in participation, wages, and happiness.' 
              : 'Geographical distribution of job mobility and worker transfers.'}
          </p>
        </div>
        <div className="view-toggle" style={{ display: 'flex', gap: '8px', background: '#e2e8f0', padding: '4px', borderRadius: '8px' }}>
          <button 
            className={`tab-link ${viewMode === 'trends' ? 'active' : ''}`}
            onClick={() => setViewMode('trends')}
            style={{ padding: '6px 12px', fontSize: '12px', minWidth: 'auto' }}
          >
            📊 Statistical Trends
          </button>
          <button 
            className={`tab-link ${viewMode === 'network' ? 'active' : ''}`}
            onClick={() => setViewMode('network')}
            style={{ padding: '6px 12px', fontSize: '12px', minWidth: 'auto' }}
          >
            🌐 Mobility Network
          </button>
        </div>
      </div>

      {loading && (
        <LoadingSpinner size="large" message="Loading comprehensive labor data..." />
      )}

      {error && (
        <ErrorState 
          message="Failed to load employment content"
          details={error}
          onRetry={fetchData}
        />
      )}

      {!loading && !error && (
        <div className="view-container" style={{ minHeight: '600px' }}>
          {viewMode === 'trends' ? (
            iframeContent && (
              <AutoResizingIframe 
                srcDoc={iframeContent} 
                title="Employment & Turnover Dashboard"
              />
            )
          ) : (
            mapData && (
              <div className="map-layout" style={{ animation: 'fadeIn 0.3s ease' }}>
                <div className="chart-card large">
                  <h3>Job Mobility Map</h3>
                  <p className="chart-note">Hover over or click an employer to reveal incoming/outgoing worker transfers.</p>
                  <BuildingsMap 
                    onEmployerSelect={handleEmployerSelect}
                    transitionData={mapData}
                    isEmploymentNetworkMap={true}
                    hideFilters={true}
                    employers={employers}
                    colorblindMode={colorblindMode}
                    onColorblindToggle={setColorblindMode}
                  />
                </div>

                <aside className="details-panel" style={{ height: 'fit-content' }}>
                  <h3>Selected Employer</h3>
                  {selectedEmployer ? (
                    <>
                      <div className="details-row"><span>Name</span><strong>{selectedEmployer.name}</strong></div>
                      <div className="details-row"><span>ID</span><strong>{selectedEmployer.id}</strong></div>
                      <div className="details-row">
                        <span>Prosperity</span>
                        <strong>
                          {(() => {
                            const emp = employers.find(e => Number(e.employerId) === Number(selectedEmployer.id));
                            const score = emp?.health_score;
                            return score !== undefined && score !== null ? `${Math.round(score * 100)}%` : 'n/a';
                          })()}
                        </strong>
                      </div>
                      
                      <div style={{ marginTop: '16px', borderTop: '1px solid #ddd', paddingTop: '12px' }}>
                        <h4 style={{ fontSize: '12px', marginBottom: '8px' }}>Worker Transfers</h4>
                        <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
                            <thead>
                              <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                                <th style={{ textAlign: 'left', padding: '4px 0' }}>Employer</th>
                                <th style={{ textAlign: 'center', padding: '4px 0' }}>In</th>
                                <th style={{ textAlign: 'center', padding: '4px 0' }}>Out</th>
                              </tr>
                            </thead>
                            <tbody>
                              {mapData.nodes
                                .map(node => {
                                  const incoming = mapData.links.find(l => String(l.target) === String(selectedEmployer.id) && String(l.source) === String(node.id));
                                  const outgoing = mapData.links.find(l => String(l.source) === String(selectedEmployer.id) && String(l.target) === String(node.id));
                                  return { node, incoming, outgoing, total: (incoming?.value || 0) + (outgoing?.value || 0) };
                                })
                                .filter(t => t.total > 0)
                                .sort((a, b) => b.total - a.total)
                                .map((t, idx) => (
                                  <tr key={idx} style={{ borderBottom: '1px solid #f0f0f0' }}>
                                    <td style={{ padding: '4px 0' }}>{t.node.name}</td>
                                    <td style={{ textAlign: 'center', color: inColor, fontWeight: '600' }}>{t.incoming ? t.incoming.value : '—'}</td>
                                    <td style={{ textAlign: 'center', color: outColor, fontWeight: '600' }}>{t.outgoing ? t.outgoing.value : '—'}</td>
                                  </tr>
                                ))
                              }
                            </tbody>
                          </table>
                        </div>
                        <div style={{ marginTop: '12px', fontSize: '10px' }}>
                          <div style={{ color: inColor }}>● Incoming transfers</div>
                          <div style={{ color: outColor }}>● Outgoing transfers</div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="chart-placeholder">Click an employer on the map to see details here.</div>
                  )}
                </aside>
              </div>
            )
          )}
        </div>
      )}
      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </section>
  );
}

export default EmploymentTurnoverPage;
