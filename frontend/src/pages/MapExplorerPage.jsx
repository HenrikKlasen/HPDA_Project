import BuildingsMap from '../components/maps/BuildingsMap';
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

function MapExplorerPage() {
  const [selectedEmployer, setSelectedEmployer] = useState(null);
  const [employers, setEmployers] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    let data = localStorage.getItem('employers');
    if (!data) {

            fetch('http://localhost:5000/api/export/employer-health-csv')
              .then(res => res.text())
              .then(data => {
                localStorage.setItem('employers', data);
              })
              .catch(error => {
                console.error('Failed to fetch business health content:', error);
              });
              data = localStorage.getItem('employers');
          }
      try {
        const parsed = JSON.parse(data);
        if (Array.isArray(parsed)) {
          setEmployers(parsed);
          console.log('Employers loaded:', parsed);
        } else {
          setSelectedEmployer(parsed);
        }
      } catch (e) {
        console.error('Failed to parse employers data:', e);
      }
        
  }, []);

  const handleEmployerSelect = (pointData) => {
    console.log('Point selected:', pointData);
    console.log('Employers data:', employers);
    
    if (pointData && pointData.name && employers.length > 0) {
      // Try multiple matching strategies
      let matchedEmployer = employers.find(
        (emp) => emp.location && emp.id.toLowerCase().equals(pointData.id.toLowerCase())
      );
      
      if (!matchedEmployer) {
        matchedEmployer = employers.find(
          (emp) => emp.employerId === pointData.id
        );
      }
      
      if (!matchedEmployer) {
        matchedEmployer = employers.find(
          (emp) => emp.employerId  == pointData.id
        );
      }
      
      console.log('Matched employer:', matchedEmployer);
      
      if (matchedEmployer) {
        setSelectedEmployer(matchedEmployer);
      } else {
        console.warn('No employer matched for point:', pointData.id);
      }
    } else {
      console.warn('Point data invalid or no employers loaded');
    }
  };

  return (
    <section>
      <div className="section-intro">
        <h2>Map Explorer</h2>
        <p>
          This tab focuses on spatial employer health, turnover, wage level, and employer size.
        </p>
      </div>

      <div className="map-layout">
        <div className="chart-card large">
          <h3>Employer Symbol Map</h3>
          <p className="chart-note">
            Large version of the map with controls for color mode and selected employer.
          </p>
          <BuildingsMap onEmployerSelect={handleEmployerSelect} />
        </div>

        <aside className="details-panel">
          <h3>Selected Employer Details</h3>

          {selectedEmployer ? (
            <>
              {Object.entries(selectedEmployer).map(([key, value]) => (
                <div className="details-row" key={key}>
                  <span>{key}</span>
                  <strong>{value || '—'}</strong>
                </div>
              ))}
              {/* Button to open EmployerDetailPage */}
              <div style={{ marginTop: '12px' }}>
                {(() => {
                  const empId = selectedEmployer.id ?? selectedEmployer.employerId ?? selectedEmployer.employer_id;
                  return empId ? (
                    <button
                      type="button"
                      className="map-chip active"
                      onClick={() => navigate(`/employer/${empId}`)}
                      title="Open employer details"
                    >
                      Open detailed info
                    </button>
                  ) : null;
                })()}
              </div>
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

export default MapExplorerPage;