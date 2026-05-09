import React, { useEffect, useState } from 'react';
import BuildingsMap from '../components/maps/BuildingsMap';

function EmploymentNetworkMapPage() {
  const [mapData, setMapData] = useState(null);
  const [selectedEmployer, setSelectedEmployer] = useState(null);
  const [employers, setEmployers] = useState([]);
  const [colorblindMode, setColorblindMode] = useState(false);
  const inColor = colorblindMode ? '#0ea5e9' : '#22c55e';
  const outColor = colorblindMode ? '#f97316' : '#ef4444';

  useEffect(() => {
    // Load employers data
    const data = localStorage.getItem('employers');
    if (data) {
      try {
        const parsed = JSON.parse(data);
        if (Array.isArray(parsed)) {
          setEmployers(parsed);
        }
      } catch (e) {
        console.error('Failed to parse employers data:', e);
      }
    }

    // Load job transitions data
    fetch('http://localhost:5000/api/job_transitions')
      .then(res => res.json())
      .then(data => {
        setMapData(data);
      })
      .catch(error => {
        console.error('Failed to fetch job transitions:', error);
      });
  }, []);

  const handleEmployerSelect = (pointData) => {
    if (pointData && mapData) {
      // Find the node in the transitions data
      const selectedNode = mapData.nodes.find(n => n.id == pointData.id);
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
      <div className="section-intro">
        <h2>Employment Network Map</h2>
        <p>
          This visualization shows the geographical distribution of employers and the flow of workers between them.
          Hover over or click an employer to see its connections.
        </p>
      </div>

      <div className="map-layout">
        <div className="chart-card large">
          <h3>Employer Transition Network on Map</h3>
          <p className="chart-note">
            Buildings shown in background. Employer points with job transition connections. 
            Hover or click to reveal connections.
          </p>
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

        <aside className="details-panel">
          <h3>Selected Employer</h3>

          {selectedEmployer ? (
            <>
              <div className="details-row">
                <span>Name</span>
                <strong>{selectedEmployer.name}</strong>
              </div>
              <div className="details-row">
                <span>ID</span>
                <strong>{selectedEmployer.id}</strong>
              </div>
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
              
              {mapData && (
                <>
                  <div style={{ marginTop: '16px', borderTop: '1px solid #ddd', paddingTop: '12px' }}>
                    <h4 style={{ fontSize: '12px', marginBottom: '8px' }}>Worker Transfers</h4>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                          <th style={{ textAlign: 'left', padding: '4px 0', fontWeight: '600' }}>Employer</th>
                          <th style={{ textAlign: 'center', padding: '4px 0', fontWeight: '600' }}>In</th>
                          <th style={{ textAlign: 'center', padding: '4px 0', fontWeight: '600' }}>Out</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(() => {
                          const transfers = mapData.nodes
                            .map(node => {
                              const incomingLink = mapData.links.find(l => l.target === selectedEmployer.id && l.source === node.id);
                              const outgoingLink = mapData.links.find(l => l.source === selectedEmployer.id && l.target === node.id);
                              return {
                                node,
                                incomingLink,
                                outgoingLink,
                                total: (incomingLink?.value || 0) + (outgoingLink?.value || 0)
                              };
                            })
                            .filter(t => t.total > 0)
                            .sort((a, b) => b.total - a.total);

                          return transfers.map((t, idx) => (
                            <tr key={idx} style={{ borderBottom: '1px solid #f0f0f0' }}>
                              <td style={{ padding: '4px 0', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {t.node.name}
                              </td>
                              <td style={{ textAlign: 'center', padding: '4px 0', color: inColor, fontWeight: '600' }}>
                                {t.incomingLink ? t.incomingLink.value : '—'}
                              </td>
                              <td style={{ textAlign: 'center', padding: '4px 0', color: outColor, fontWeight: '600' }}>
                                {t.outgoingLink ? t.outgoingLink.value : '—'}
                              </td>
                            </tr>
                          ));
                        })()}
                      </tbody>
                    </table>
                    <div style={{ marginTop: '8px', fontSize: '10px', color: '#6b7280' }}>
                      <div style={{ color: inColor, fontWeight: '600' }}>● In = Incoming transfers</div>
                      <div style={{ color: outColor, fontWeight: '600' }}>● Out = Outgoing transfers</div>
                    </div>
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="chart-placeholder" style={{ marginTop: '18px', minHeight: '160px' }}>
              Click an employer on the map to see details here.
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}

export default EmploymentNetworkMapPage;
