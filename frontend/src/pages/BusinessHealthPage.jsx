function BusinessHealthPage() {
  return (
    <section>
      <div className="section-intro">
        <h2>Business Health</h2>
        <p>
          This tab focuses on which businesses appear prosperous, stable, declining, or struggling.
          Any business health score is clearly labeled as derived or estimated.
        </p>
      </div>

      <iframe
        src="http://localhost:5000/api/business-health-page"
        style={{ width: '100%', height: '1000px', border: 'none', display: 'block' }}
        title="Business Health Dashboard"
      />
    </section>
  );
}

export default BusinessHealthPage;
