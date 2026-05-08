import React, { useMemo, useEffect, useState } from 'react';

function EmploymentTurnoverPage() {
    const [iframeContent, setIframeContent] = useState(null);
  
    useEffect(() => {
      const cachedContent = localStorage.getItem('residentFinancialContent');
      if (cachedContent) {
        setIframeContent(cachedContent);
      } else {
        fetch('http://localhost:5000/api/resident-financial-page')
          .then(res => res.text())
          .then(html => {
            localStorage.setItem('residentFinancialContent', html);
            setIframeContent(html);
          })
          .catch(error => {
            console.error('Failed to fetch resident financial content:', error);
          });
      }
    }, []);
  
  return (
    <section>
      <div className="section-intro">
        <h2>Employment &amp; Turnover</h2>
        <p>
          Employer stability, worker movement, job turnover, and changes in labor participation over time.
        </p>
      </div>

      {iframeContent && (
        <iframe srcDoc={iframeContent} style={{ width: '100%', height: '2000px', border: 'none' }} />
      )}
  
    </section>
  );
}

export default EmploymentTurnoverPage;
