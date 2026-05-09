import { useMemo, useState, useEffect } from 'react';

function BusinessHealthPage() {
  const [iframeContent, setIframeContent] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const cachedContent = localStorage.getItem('businessHealthContent');
    if (cachedContent) {
      setIframeContent(cachedContent);
      setLoading(false);
    } else {
      fetch('http://localhost:5000/api/business-health-page')
        .then(res => res.text())
        .then(html => {
          localStorage.setItem('businessHealthContent', html);
          setIframeContent(html);
          setLoading(false);
        })
        .catch(error => {
          console.error('Failed to fetch business health content:', error);
          setLoading(false);
        });
    }
  }, []);

  return (
    <section>
      <div className="section-intro">
        <h2>Business Health</h2>
        <p>
          This tab focuses on which businesses appear prosperous, stable, declining, or struggling.
          Any business health score is clearly labeled as derived or estimated.
        </p>
      </div>
      {loading && (
        <div style={{ padding: '60px', textAlign: 'center', background: '#fff', borderRadius: '8px', margin: '20px' }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>⏳</div>
          <div style={{ fontSize: '16px', color: '#666' }}>Generating business health analysis...</div>
          <div style={{ fontSize: '12px', color: '#999', marginTop: '8px' }}>Rendering visualizations and metrics</div>
        </div>
      )}
      {iframeContent && (
        <iframe srcDoc={iframeContent} style={{ width: '100%', height: '2000px', border: 'none' }} />
      )}
    </section>
  );
}

export default BusinessHealthPage;