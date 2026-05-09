import React, { useEffect, useState } from "react";
import LoadingSpinner from "../components/common/LoadingSpinner";
import ErrorState from "../components/common/ErrorState";
import AutoResizingIframe from "../components/common/AutoResizingIframe";

function OverallViewPage() {
  const [iframeContent, setIframeContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchContent = () => {
    setLoading(true);
    setError(null);

    const cachedContent = localStorage.getItem("overallViewContent");
    if (cachedContent) {
      setIframeContent(cachedContent);
      setLoading(false);
    } else {
      fetch("http://localhost:5000/api/overall-view-page")
        .then((res) => {
          if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
          }
          return res.text();
        })
        .then((html) => {
          localStorage.setItem("overallViewContent", html);
          setIframeContent(html);
          setLoading(false);
        })
        .catch((err) => {
          console.error("Failed to fetch overall view content:", err);
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
      {loading && (
        <LoadingSpinner
          size="large"
          message="Loading overall view dashboard..."
        />
      )}

      {error && (
        <ErrorState
          message="Failed to load overall view content"
          details={error}
          onRetry={fetchContent}
        />
      )}

      {!loading && !error && iframeContent && (
        <AutoResizingIframe
          srcDoc={iframeContent}
          title="Overall View Dashboard"
          style={{
            borderRadius: "12px",
            boxShadow: "var(--shadow)",
          }}
        />
      )}
    </section>
  );
}

export default OverallViewPage;
