import { useState, useEffect } from "react";
import LoadingSpinner from "../components/common/LoadingSpinner";
import ErrorState from "../components/common/ErrorState";
import AutoResizingIframe from "../components/common/AutoResizingIframe";

function ResidentFinancialHealthPage() {
  const [iframeContent, setIframeContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchContent = () => {
    setLoading(true);
    setError(null);

    const cachedContent = localStorage.getItem("residentFinancialContent");
    if (cachedContent) {
      setIframeContent(cachedContent);
      setLoading(false);
    } else {
      fetch("http://localhost:5000/api/resident-financial-page")
        .then((res) => {
          if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
          }
          return res.text();
        })
        .then((html) => {
          localStorage.setItem("residentFinancialContent", html);
          setIframeContent(html);
          setLoading(false);
        })
        .catch((err) => {
          console.error("Failed to fetch resident financial content:", err);
          setError(err.message);
          setLoading(false);
        });
    }
  };

  useEffect(() => {
    fetchContent();
  }, []);

  return (
    <section>
      <div className="section-intro">
        <h2>Resident Vitality & Financial Well-being</h2>
        <p>
          Wages, expenses, net income, cost of living, and resident groups with
          similar patterns.
        </p>
      </div>

      {loading && (
        <LoadingSpinner
          size="large"
          message="Loading resident financial data..."
        />
      )}

      {error && (
        <ErrorState
          message="Failed to load resident financial health content"
          details={error}
          onRetry={fetchContent}
        />
      )}

      {!loading && !error && iframeContent && (
        <AutoResizingIframe
          srcDoc={iframeContent}
          title="Resident Financial Health Dashboard"
        />
      )}
    </section>
  );
}

export default ResidentFinancialHealthPage;
