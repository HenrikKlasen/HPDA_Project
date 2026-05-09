function LoadingSkeleton({ type = 'card', count = 1 }) {
  const skeletons = Array.from({ length: count }, (_, i) => i);

  if (type === 'kpi') {
    return (
      <div className="kpi-grid">
        {skeletons.map((i) => (
          <div key={i} className="skeleton-kpi">
            <div className="skeleton-line skeleton-line-short"></div>
            <div className="skeleton-line skeleton-line-medium"></div>
          </div>
        ))}
      </div>
    );
  }

  if (type === 'chart') {
    return (
      <div className="chart-grid">
        {skeletons.map((i) => (
          <div key={i} className="skeleton-chart">
            <div className="skeleton-line skeleton-line-medium"></div>
            <div className="skeleton-chart-area"></div>
          </div>
        ))}
      </div>
    );
  }

  // Default card skeleton
  return (
    <div className="skeleton-card">
      <div className="skeleton-line skeleton-line-long"></div>
      <div className="skeleton-line skeleton-line-medium"></div>
      <div className="skeleton-line skeleton-line-short"></div>
    </div>
  );
}

export default LoadingSkeleton;
