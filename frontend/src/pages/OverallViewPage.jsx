import { useMemo, useEffect, useState } from 'react';

function OverallViewPage() {
  const [iframeContent, setIframeContent] = useState(null);

  useEffect(() => {
    const cachedContent = localStorage.getItem('overallViewContent');
    if (cachedContent) {
      setIframeContent(cachedContent);
    } else {
      fetch('http://localhost:5000/api/overall-view-page')
        .then(res => res.text())
        .then(html => {
          localStorage.setItem('overallViewContent', html);
          setIframeContent(html);
        })
        .catch(error => {
          console.error('Failed to fetch overall view content:', error);
        });
    }
  }, []);

  return (
    <section>
      <div className="section-intro">
        <h2>Overall View</h2>
        <p>
          Main summary evidence for the three challenge questions — KPIs, wages vs cost of living,
          employer health ranking, prosperity scatter, and spatial map.
        </p>
      </div>

      {iframeContent && (
        <iframe srcDoc={iframeContent} style={{ width: '100%', height: '2000px', border: 'none' }} />
      )}
    </section>
  );
}

export default OverallViewPage;
