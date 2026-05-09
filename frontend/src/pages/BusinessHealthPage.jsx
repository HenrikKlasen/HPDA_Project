import { useState, useEffect } from "react";
import LoadingSpinner from "../components/common/LoadingSpinner";
import AutoResizingIframe from "../components/common/AutoResizingIframe";

function BusinessHealthPage() {
  const [iframeContent, setIframeContent] = useState(null);
  const [loading, setLoading] = useState(true);
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
  }, []);

  return (
    <section>
      {loading && (
        <LoadingSpinner message="Generating business health analysis..." />
      )}
      {iframeContent && (
        <AutoResizingIframe
          srcDoc={iframeContent}
          title="Business Health Dashboard"
        />
      )}
    </section>
  );
}

export default BusinessHealthPage;
