import * as d3 from 'd3';
import { useEffect, useMemo, useState } from 'react';
import LoadingSpinner from '../common/LoadingSpinner';
import ErrorState from '../common/ErrorState';

const CATEGORY_COLORS = {
  Employer: '#2563eb',
  Restaurant: '#ef4444',
  Pub: '#f59e0b',
  School: '#10b981',
};

function CityPointsMap() {
  const [points, setPoints] = useState([]);
  const [buildings, setBuildings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activePoint, setActivePoint] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [showBuildings, setShowBuildings] = useState(true);
  const [enabledCategories, setEnabledCategories] = useState({
    Employer: true,
    Restaurant: true,
    Pub: true,
    School: true,
  });

  useEffect(() => {
    let ignore = false;

    async function loadData() {
      setLoading(true);
      setError('');
      try {
        const rows = await d3.csv('/data/map_points.csv', (row) => ({
          id: row.id,
          name: row.name,
          category: row.category,
          x: Number(row.x),
          y: Number(row.y),
        }));

        const buildingResponse = await fetch('/data/buildings.json');
        const buildingData = await buildingResponse.json();

        if (!ignore) {
          setPoints(rows.filter((row) => Number.isFinite(row.x) && Number.isFinite(row.y)));
          setBuildings(buildingData || []);
        }
      } catch {
        if (!ignore) setError('Unable to load map data.');
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    loadData();

    return () => {
      ignore = true;
    };
  }, []);

  const filteredPoints = useMemo(
    () => points.filter((point) => enabledCategories[point.category]),
    [points, enabledCategories]
  );

  const mapWidth = 1076;
  const mapHeight = 1144;
  const displayWidth = 760;
  const displayHeight = Math.round((displayWidth / mapWidth) * mapHeight);

  // Calculate actual data coordinate ranges from both points and buildings
  const allX = [...points.map((p) => p.x), ...buildings.flatMap((b) => b.coords.map((c) => c[0]))];
  const allY = [...points.map((p) => p.y), ...buildings.flatMap((b) => b.coords.map((c) => c[1]))];
  const xExtent = d3.extent(allX);
  const yExtent = d3.extent(allY);

  const x = d3
    .scaleLinear()
    .domain([xExtent[0] ?? 0, xExtent[1] ?? 1])
    .range([0, displayWidth]);

  const y = d3
    .scaleLinear()
    .domain([yExtent[0] ?? 0, yExtent[1] ?? 1])
    .range([displayHeight, 0]);

  const categories = ['Employer', 'Restaurant', 'Pub', 'School'];

  function toggleCategory(category) {
    setEnabledCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  }

  return (
    <article className="card map-card">
      <div className="map-header">
        <h2 className="chart-title">City Map (buildings + points)</h2>
        <p className="map-subtitle">Interactive building polygons and location points. Toggle layers to filter.</p>
      </div>

      <div className="map-filters" role="group" aria-label="Map layer filters">
        <button
          type="button"
          className={`map-chip${showBuildings ? ' active' : ''}`}
          onClick={() => setShowBuildings(!showBuildings)}
        >
          <span className="map-chip-dot" style={{ background: '#94a3b8' }} />
          Buildings
        </button>
        {categories.map((category) => (
          <button
            key={category}
            type="button"
            className={`map-chip${enabledCategories[category] ? ' active' : ''}`}
            onClick={() => toggleCategory(category)}
          >
            <span className="map-chip-dot" style={{ background: CATEGORY_COLORS[category] }} />
            {category}
          </button>
        ))}
      </div>

      {loading && <LoadingSpinner size="medium" message="Loading map data..." />}
      {error && <ErrorState message={error} showRetry={false} />}

      {!loading && !error && (
        <div className="chart-wrap" style={{ position: 'relative' }}>
          <svg viewBox={`0 0 ${displayWidth} ${displayHeight}`} className="chart-svg map-svg" role="img" aria-label="City map with buildings and points">
            <image href="/assets/basemap.png" x="0" y="0" width={displayWidth} height={displayHeight} />

            {showBuildings &&
              buildings.map((building) => {
                const pathData = building.coords
                  .map((coord, i) => `${i === 0 ? 'M' : 'L'} ${x(coord[0])} ${y(coord[1])}`)
                  .join(' ');
                const fillColor = building.type === 'Commercial' ? '#dbeafe' : building.type === 'School' ? '#dbeafe' : '#f0fdf4'; // Handles "Residential" and "Residental"
                return (
                  <path
                    key={`building-${building.id}`}
                    d={pathData}
                    fill={fillColor}
                    stroke="#cbd5e0"
                    strokeWidth="0.8"
                    opacity="0.65"
                  />
                );
              })}

            {filteredPoints.map((point) => (
              <circle
                key={`${point.category}-${point.id}`}
                cx={x(point.x)}
                cy={y(point.y)}
                r={activePoint?.id === point.id && activePoint?.category === point.category ? 6 : 3.5}
                fill={CATEGORY_COLORS[point.category]}
                fillOpacity={0.88}
                stroke="#ffffff"
                strokeWidth="1.2"
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setActivePoint(point)}
                onMouseMove={(e) => {
                  const rect = e.currentTarget.closest('.chart-wrap').getBoundingClientRect();
                  setTooltipPos({
                    x: e.clientX - rect.left + 10,
                    y: e.clientY - rect.top + 10,
                  });
                }}
                onMouseLeave={() => setActivePoint(null)}
              />
            ))}
          </svg>

          {activePoint && (
            <div
              className="chart-tooltip"
              role="status"
              style={{
                position: 'absolute',
                left: `${tooltipPos.x}px`,
                top: `${tooltipPos.y}px`,
                pointerEvents: 'none',
              }}
            >
              <strong>{activePoint.name}</strong>
              <span>{activePoint.category}</span>
              <span>
                ({activePoint.x.toFixed(1)}, {activePoint.y.toFixed(1)})
              </span>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export default CityPointsMap;
