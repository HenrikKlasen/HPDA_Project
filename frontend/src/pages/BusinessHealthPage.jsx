import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import LoadingSpinner from "../components/common/LoadingSpinner";
import AutoResizingIframe from "../components/common/AutoResizingIframe";
import BuildingsMap from "../components/maps/BuildingsMap";

function BusinessHealthPage() {
  const [iframeContent, setIframeContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const location = useLocation();
  const [viewMode, setViewMode] = useState(location.state?.viewMode || "trends"); // 'trends' or 'map'
  const [employers, setEmployers] = useState([]);
  const [selectedEmployerId, setSelectedEmployerId] = useState(location.state?.selectedEmployerId || null);
  const navigate = useNavigate();

  useEffect(() => {
    const handleMessage = (event) => {
      if (event.data && event.data.type === "EMPLOYER_SELECTED") {
        setSelectedEmployerId(event.data.employerId);
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  useEffect(() => {
    const cachedContent = localStorage.getItem("businessHealthContent");
    if (cachedContent) {
      setIframeContent(cachedContent);
      setLoading(false);
    } else {
      fetch("http://localhost:5000/api/business-health-page")
        .then((res) => res.text())
        .then((html) => {
          localStorage.setItem("businessHealthContent", html);
          setIframeContent(html);
          setLoading(false);
        })
        .catch((error) => {
          console.error("Failed to fetch business health content:", error);
          setLoading(false);
        });
    }

    let data = localStorage.getItem("employers");
    if (!data) {
      fetch("http://localhost:5000/api/export/employer-health-csv")
        .then((res) => res.text())
        .then((data) => {
          localStorage.setItem("employers", data);
          try {
            const parsed = JSON.parse(data);
            if (Array.isArray(parsed)) setEmployers(parsed);
          } catch (e) {}
        })
        .catch((error) => {
          console.error("Failed to fetch employers:", error);
        });
    } else {
      try {
        const parsed = JSON.parse(data);
        if (Array.isArray(parsed)) setEmployers(parsed);
      } catch (e) {}
    }
  }, []);

  const handleObjectSelect = (pointData) => {
    if (pointData && pointData.category === "Employer") {
      navigate(`/employer/${pointData.id}/financials`);
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
          <h2>Enterprise Health Dashboard</h2>
          <p>
            {viewMode === "trends"
              ? "City-wide trends in business health. Click any employer in any chart to highlight it across all views."
              : "Geographical distribution and explorer map."}
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
            className={`tab-link ${viewMode === "map" ? "active" : ""}`}
            onClick={() => setViewMode("map")}
            style={{ padding: "6px 12px", fontSize: "12px", minWidth: "auto" }}
          >
            Explorer Map
          </button>
        </div>
      </div>

      {loading && (
        <LoadingSpinner message="Generating business health analysis..." />
      )}

      {!loading && (
        <div className="view-container" style={{ minHeight: "600px" }}>
          {viewMode === "trends" ? (
            iframeContent && (
              <AutoResizingIframe
                srcDoc={iframeContent}
                title="Business Health Dashboard"
              />
            )
          ) : (
            <div
              className="chart-card large"
              style={{ animation: "fadeIn 0.3s ease" }}
            >
              <p className="chart-note">
                Click on an employer point on the map to view detailed financial
                insights and performance metrics.
              </p>
              <BuildingsMap
                onEmployerSelect={handleObjectSelect}
                initialSelectedEmployerId={selectedEmployerId}
              />
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default BusinessHealthPage;
