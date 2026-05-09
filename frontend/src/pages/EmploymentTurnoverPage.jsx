import { useEffect, useState } from 'react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorState from '../components/common/ErrorState';
import AutoResizingIframe from '../components/common/AutoResizingIframe';

function EmploymentTurnoverPage() {
  const [iframeContent, setIframeContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchContent = () => {
    setLoading(true);
    setError(null);
    
    const cachedContent = localStorage.getItem('employmentContent');
    if (cachedContent) {
      setIframeContent(cachedContent);
      setLoading(false);
    } else {
      fetch('http://localhost:5000/api/employment-page')
        .then(res => {
          if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
          }
          return res.text();
        })
        .then(html => {
          localStorage.setItem('employmentContent', html);
          setIframeContent(html);
          setLoading(false);
        })
        .catch(err => {
          console.error('Failed to fetch employment turnover content:', err);
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
        <h2>
          Employment &amp; Turnover
          
        </h2>
        <p>
          Employer stability, worker movement, job turnover, and changes in labor participation over time.
        </p>
      </div>

      {loading && (
        <LoadingSpinner size="large" message="Loading employment turnover data..." />
      )}

      {error && (
        <ErrorState 
          message="Failed to load employment turnover content"
          details={error}
          onRetry={fetchContent}
        />
      )}

      {!loading && !error && iframeContent && (
        <AutoResizingIframe 
          srcDoc={iframeContent} 
          title="Employment & Turnover Dashboard"
        />
      )}
    </section>
  );
}

export default EmploymentTurnoverPage;
