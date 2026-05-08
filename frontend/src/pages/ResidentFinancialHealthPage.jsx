import React, { useMemo, useState, useEffect } from 'react';
function ResidentFinancialHealthPage() {

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
        <h2>Resident Financial Health</h2>
        <p>
          Wages, expenses, net income, cost of living, and resident groups with similar patterns.
          FinancialJournal is interpreted as participant income and spending.
        </p>
      </div>


      {iframeContent && (
        <iframe srcDoc={iframeContent} style={{ width: '100%', height: '2000px', border: 'none' }} />
      )}
    </section>
  );
}

export default ResidentFinancialHealthPage;
