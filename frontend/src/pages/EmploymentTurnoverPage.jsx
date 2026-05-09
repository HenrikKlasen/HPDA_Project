import React, { useEffect, useState } from "react";
import LoadingSpinner from "../components/common/LoadingSpinner";
import ErrorState from "../components/common/ErrorState";
import AutoResizingIframe from "../components/common/AutoResizingIframe";
import BuildingsMap from "../components/maps/BuildingsMap";

function EmploymentTurnoverPage() {
  const [iframeContent, setIframeContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState("trends"); // 'trends' or 'network'

  // Transition Map states
  const [mapData, setMapData] = useState(null);
  const [selectedEmployer, setSelectedEmployer] = useState(null);
  const [employers, setEmployers] = useState([]);
  const [colorblindMode, setColorblindMode] = useState(false);

  const inColor = colorblindMode ? "#0ea5e9" : "#22c55e";
  const outColor = colorblindMode ? "#f97316" : "#ef4444";

  const fetchData = async () => {
    setLoading(true);
    setError(null);

    try {
      // 1. Fetch Trends (Iframe)
      const cachedContent = localStorage.getItem("employmentContent");
      if (cachedContent) {
        setIframeContent(cachedContent);
      } else {
        const res = await fetch("http://localhost:5000/api/employment-page");
        if (!res.ok) throw new Error(`Trends API error: ${res.status}`);
        const html = await res.text();
        localStorage.setItem("employmentContent", html);
        setIframeContent(html);
      }

      // 2. Fetch Network Data (JSON)
      const networkRes = await fetch(
        "http://localhost:5000/api/job_transitions",
      );
      if (!networkRes.ok)
        throw new Error(`Network API error: ${networkRes.status}`);
      const nData = await networkRes.json();
      setMapData(nData);

      // 3. Load employers from localStorage
      const empData = localStorage.getItem("employers");
      if (empData) {
        const parsed = JSON.parse(empData);
        if (Array.isArray(parsed)) setEmployers(parsed);
      }

      setLoading(false);
    } catch (err) {
      console.error("Failed to fetch employment data:", err);
      setError(err.message);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleEmployerSelect = (pointData) => {
    if (pointData && mapData) {
      const selectedNode = mapData.nodes.find(
        (n) => String(n.id) === String(pointData.id),
      );
      if (selectedNode) {
        setSelectedEmployer({
          id: selectedNode.id,
          name: selectedNode.name,
          x: selectedNode.x,
          y: selectedNode.y,
        });
      }
    }
  };

  return (
    <section>
      <div
        className="section-intro"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h2>Labor Dynamics & Workforce Pulse</h2>
          <p>
            {viewMode === "trends"
              ? "City-wide trends in participation, wages, and happiness."
              : "Geographical distribution of job mobility and worker transfers."}
          </p>
        </div>
        <div
          className="view-toggle"
          style={{
            display: "flex",
            gap: "8px",
            background: "#e2e8f0",
            padding: "4px",
            borderRadius: "8px",
          }}
        >
          <button
            className={`tab-link ${viewMode === "trends" ? "active" : ""}`}
            onClick={() => setViewMode("trends")}
            style={{ padding: "6px 12px", fontSize: "12px", minWidth: "auto" }}
          >
            Statistical Trends
          </button>
          <button
            className={`tab-link ${viewMode === "network" ? "active" : ""}`}
            onClick={() => setViewMode("network")}
            style={{ padding: "6px 12px", fontSize: "12px", minWidth: "auto" }}
          >
            Mobility Network
          </button>
        </div>
      </div>

      {loading && (
        <LoadingSpinner
          size="large"
          message="Loading comprehensive labor data..."
        />
      )}

      {error && (
        <ErrorState
          message="Failed to load employment content"
          details={error}
          onRetry={fetchData}
        />
      )}

      {!loading && !error && (
        <div className="view-container" style={{ minHeight: "600px" }}>
          {viewMode === "trends"
            ? iframeContent && (
                <AutoResizingIframe
                  srcDoc={iframeContent}
                  title="Employment & Turnover Dashboard"
                />
              )
            : mapData && (
                <div
                  className="chart-card large"
                  style={{ animation: "fadeIn 0.3s ease" }}
                >
                  <p className="chart-note">
                    Hover over or click an employer to reveal incoming/outgoing
                    worker transfers.
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
