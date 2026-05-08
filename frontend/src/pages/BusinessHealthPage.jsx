import { useMemo, useState, useEffect } from 'react';

function BusinessHealthPage() {
  const [iframeContent, setIframeContent] = useState(null);

  useEffect(() => {
          const cachedContent = localStorage.getItem('businessHealthContent');
          if (cachedContent) {
            setIframeContent(cachedContent);
          } else {
            fetch('http://localhost:5000/api/business-health-page')
              .then(res => res.text())
              .then(html => {
                localStorage.setItem('businessHealthContent', html);
                setIframeContent(html);
              })
              .catch(error => {
                console.error('Failed to fetch business health content:', error);
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
      {iframeContent && (
        <iframe srcDoc={iframeContent} style={{ width: '100%', height: '2000px', border: 'none' }} />
      )}
    </section>
  );
}

export default BusinessHealthPage;