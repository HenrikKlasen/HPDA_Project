import * as d3 from 'd3';
import { useEffect, useMemo, useRef, useState } from 'react';

const CATEGORY_COLORS = {
  Employer: '#0051ffff',
  Restaurant: '#ff0000ff',
  Pub: '#f50bcaff',
  School: '#f59e0b',
};

function BuildingsMap() {
  const svgRef = useRef(null);
  const groupRef = useRef(null);
  const zoomBehaviorRef = useRef(null);
  const [buildings, setBuildings] = useState([]);
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeBuilding, setActiveBuilding] = useState(null);
  const [activePoint, setActivePoint] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [zoomLevel, setZoomLevel] = useState(1);
  const [enabledTypes, setEnabledTypes] = useState({
    Commercial: true,
    Residental: true,
    School: true,
  });
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
        const buildingResponse = await fetch('/data/buildings.json');
        const buildingData = await buildingResponse.json();

        const pointRows = await d3.csv('/data/map_points.csv', (row) => ({
          id: row.id,
          name: row.name,
          category: row.category,
          x: Number(row.x),
          y: Number(row.y),
        }));

        if (!ignore) {
          setBuildings(buildingData || []);
          setPoints(pointRows.filter((row) => Number.isFinite(row.x) && Number.isFinite(row.y)));
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

useEffect(() => {
  if (loading) return;
  if (!svgRef.current || !groupRef.current) return;

  const svg = d3.select(svgRef.current);
  const group = d3.select(groupRef.current);

  const zoom = d3.zoom()
    .scaleExtent([0.5, 8])
    .on('zoom', (event) => {
      group.attr('transform', event.transform);
      setZoomLevel(event.transform.k);
    });

  zoomBehaviorRef.current = zoom;

  svg.call(zoom);

  return () => {
    svg.on('.zoom', null);
  };
}, [loading]);
function handleZoom(direction) {
  if (!svgRef.current || !zoomBehaviorRef.current) return;

  const factor = direction === 'in' ? 1.5 : 1 / 1.5;
  const newScale = Math.max(0.5, Math.min(8, zoomLevel * factor));

  d3.select(svgRef.current)
    .transition()
    .duration(300)
    .call(
      zoomBehaviorRef.current.scaleTo,
      newScale
    );
}
function resetZoom() {
  if (!svgRef.current || !zoomBehaviorRef.current) return;

  d3.select(svgRef.current)
    .transition()
    .duration(300)
    .call(zoomBehaviorRef.current.transform, d3.zoomIdentity);
}

  const filteredBuildings = useMemo(
    () => buildings.filter((building) => enabledTypes[building.type]),
    [buildings, enabledTypes]
  );

  const filteredPoints = useMemo(
    () => points.filter((point) => enabledCategories[point.category]),
    [points, enabledCategories]
  );

  const mapWidth = 1076;
  const mapHeight = 1144;
  const displayWidth = 900;
  const displayHeight = Math.round((displayWidth / mapWidth) * mapHeight);

  // Calculate data coordinate ranges from both buildings and points
  const allX = [...buildings.flatMap((b) => b.coords.map((c) => c[0])), ...points.map((p) => p.x)];
  const allY = [...buildings.flatMap((b) => b.coords.map((c) => c[1])), ...points.map((p) => p.y)];
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

  const buildingTypes = ['Commercial', 'Residental', 'School'];
  const typeColors = {
    Commercial: '#3b82f6',
    Residental: '#007850ff',
    School: '#f59e0b',
  };

  function toggleType(type) {
    setEnabledTypes((prev) => ({
      ...prev,
      [type]: !prev[type],
    }));
  }

  function toggleCategory(category) {
    setEnabledCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  }

  function handleZoom(direction) {
    console.log('handleZoom called with direction:', direction);
    console.log('groupRef.current:', groupRef.current);
    
    if (!groupRef.current) {
      console.log('Early return: missing groupRef');
      return;
    }
    
    const group = d3.select(groupRef.current);
    const newScale = direction === 'in' ? zoomLevel * 1.5 : zoomLevel / 1.5;
    const clampedScale = Math.max(0.5, Math.min(8, newScale));
    
    console.log('Current zoom level:', zoomLevel);
    console.log('New scale (before clamp):', newScale);
    console.log('Clamped scale:', clampedScale);
    
    // Create new transform with the clamped scale, keeping x and y at 0
    const newTransform = d3.zoomIdentity.scale(clampedScale);
    console.log('New transform:', newTransform);
    
    // Apply the transform to the group
    group.transition()
      .duration(300)
      .attr('transform', newTransform);
    
    setZoomLevel(clampedScale);
    console.log('Transform applied, zoom level updated to:', clampedScale);
  }

  function resetZoom() {
    console.log('resetZoom called');
    console.log('groupRef.current:', groupRef.current);
    
    if (!groupRef.current) {
      console.log('Early return: missing groupRef');
      return;
    }
    
    const group = d3.select(groupRef.current);
    const identityTransform = d3.zoomIdentity;
    
    console.log('Applying identity transform');
    
    group.transition()
      .duration(300)
      .attr('transform', identityTransform);
    
    setZoomLevel(1);
    console.log('Transform reset to identity, zoom level reset to 1');
  }

  const buildingCounts = {
    Commercial: buildings.filter((b) => b.type === 'Commercial').length,
    Residental: buildings.filter((b) => b.type === 'Residental').length,
    School: buildings.filter((b) => b.type === 'School').length,
  };

  const pointCounts = {
    Employer: points.filter((p) => p.category === 'Employer').length,
    Restaurant: points.filter((p) => p.category === 'Restaurant').length,
    Pub: points.filter((p) => p.category === 'Pub').length,
    School: points.filter((p) => p.category === 'School').length,
  };

  return (
    <article className="card map-card">
      <div className="map-header">
        <h2 className="chart-title">Building Polygons & Locations Map</h2>
        <p className="map-subtitle">
          {filteredBuildings.length} of {buildings.length} buildings, {filteredPoints.length} of {points.length} points visible.
        </p>
      </div>

      <div className="map-filters" role="group" aria-label="Building and location filters">
        <div style={{ marginBottom: '0.8rem' }}>
          <p style={{ fontSize: '0.85rem', fontWeight: '600', marginBottom: '0.4rem', color: '#6b7280' }}>Buildings</p>
          {buildingTypes.map((type) => (
            <button
              key={type}
              type="button"
              className={`map-chip${enabledTypes[type] ? ' active' : ''}`}
              onClick={() => toggleType(type)}
            >
              <span className="map-chip-dot" style={{ background: typeColors[type] }} />
              {type} ({buildingCounts[type]})
            </button>
          ))}
        </div>
        <div>
          <p style={{ fontSize: '0.85rem', fontWeight: '600', marginBottom: '0.4rem', color: '#6b7280' }}>Locations</p>
          {['Employer', 'Restaurant', 'Pub', 'School'].map((category) => (
            <button
              key={category}
              type="button"
              className={`map-chip${enabledCategories[category] ? ' active' : ''}`}
              onClick={() => toggleCategory(category)}
            >
              <span className="map-chip-dot" style={{ background: CATEGORY_COLORS[category] }} />
              {category} ({pointCounts[category]})
            </button>
          ))}
        </div>
      </div>

      {loading && <p>Loading building data...</p>}
      {error && <p>{error}</p>}

      {!loading && !error && (
        <div className="chart-wrap" style={{ position: 'relative', marginBottom: '1rem', width: '100%', height: '1000px', overflow: 'hidden' }}>
          <div style={{ marginBottom: '0.5rem', display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              className="map-chip active"
              onClick={() => handleZoom('in')}
              title="Zoom in"
            >
              🔍+
            </button>
            <button
              type="button"
              className="map-chip active"
              onClick={() => handleZoom('out')}
              title="Zoom out"
            >
              🔍−
            </button>
            <button
              type="button"
              className="map-chip active"
              onClick={resetZoom}
              title="Reset zoom"
            >
              ⟲
            </button>
            <span style={{ marginLeft: 'auto', padding: '0.45rem 0.6rem', fontSize: '0.8rem', color: '#6b7280' }}>
              Zoom: {(zoomLevel * 100).toFixed(0)}%
            </span>
          </div>
          <svg
            ref={svgRef}
            width={displayWidth}
            height={displayHeight}
            viewBox={`0 0 ${displayWidth} ${displayHeight}`}
            className="chart-svg map-svg"
            role="img"
            aria-label="Map of building polygons"
            style={{ overflow: 'hidden', cursor: 'grab', border: '1px solid #e5e7eb', display: 'block', touchAction: 'none' }}
          >
            <g ref={groupRef}>
              <rect width={displayWidth} height={displayHeight} fill="transparent" style={{ pointerEvents: 'all' }} />
              <image href="/assets/basemap.png" x="0" y="0" width={displayWidth} height={displayHeight} style={{ pointerEvents: 'all' }} />
              
              {/* Interactive layer - buildings and points */}
              {filteredBuildings.map((building) => {
                const pathData = building.coords
                  .map((coord, i) => `${i === 0 ? 'M' : 'L'} ${x(coord[0])} ${y(coord[1])}`)
                  .join(' ');
                const isActive = activeBuilding?.id === building.id;
                return (
                  <path
                    key={`building-${building.id}`}
                    d={pathData}
                    fill={typeColors[building.type]}
                    stroke={isActive ? '#ffffff' : '#1f2937'}
                    strokeWidth={isActive ? '2' : '0.8'}
                    opacity={isActive ? 0.9 : 0.6}
                    style={{ cursor: 'pointer', transition: 'all 0.2s ease', pointerEvents: 'auto' }}
                    onMouseEnter={() => setActiveBuilding(building)}
                    onMouseMove={(e) => {
                      const rect = e.currentTarget.closest('.chart-wrap').getBoundingClientRect();
                      setTooltipPos({
                        x: e.clientX - rect.left + 10,
                        y: e.clientY - rect.top + 10,
                      });
                    }}
                    onMouseLeave={() => setActiveBuilding(null)}
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
                  style={{ cursor: 'pointer', pointerEvents: 'auto' }}
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
            </g>
          </svg>

          {(activeBuilding || activePoint) && (
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
              {activeBuilding && (
                <>
                  <strong>Building {activeBuilding.id}</strong>
                  <span className="tooltip-type">{activeBuilding.type}</span>
                  <span className="tooltip-coords">
                    {activeBuilding.coords.length} vertices
                  </span>
                </>
              )}
              {activePoint && (
                <>
                  <strong>{activePoint.name}</strong>
                  <span>{activePoint.category}</span>
                  <span>
                    ({activePoint.x.toFixed(1)}, {activePoint.y.toFixed(1)})
                  </span>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export default BuildingsMap;
