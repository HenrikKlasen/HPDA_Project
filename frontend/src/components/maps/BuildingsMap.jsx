import * as d3 from 'd3';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const CATEGORY_COLORS = {
  Employer: '#0051ffff',
  Restaurant: '#ff0000ff',
  Pub: '#f50bcaff',
  School: '#f59e0b',
};

// Animated pin styles
const PIN_STYLES = `
  @keyframes pinPulse {
    0% {
      transform: scale(1);
      stroke-opacity: 0.9;
    }
    60% {
      transform: scale(2.4);
      stroke-opacity: 0.15;
    }
    100% {
      transform: scale(2.6);
      stroke-opacity: 0;
    }
  }

  @keyframes pinPing {
    0% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.15); opacity: 0.6; }
    100% { transform: scale(1); opacity: 1; }
  }

  .selected-pin-pulse {
    transform-box: fill-box;
    transform-origin: center;
    animation: pinPulse 1.6s cubic-bezier(0.4, 0, 0.2, 1) infinite;
    stroke-width: 2px;
  }

  .selected-pin-center {
    transform-box: fill-box;
    transform-origin: center;
    animation: pinPing 1.6s ease-in-out infinite;
  }

  /* Deactivated building appearance: show as gray and subdued */
  .building-deactivated {
    fill: #9ca3af !important;       /* neutral gray */
    stroke: #6b7280 !important;     /* muted stroke */
    stroke-width: 0.8 !important;
    opacity: 0.65 !important;
    transition: all 0.15s ease !important;
    pointer-events: none !important; /* optionally non-interactive */
  }
`;

function BuildingsMap({ onEmployerSelect, transitionData, isEmploymentNetworkMap = false, hideFilters = false, employers = [], colorblindMode: colorblindModeProp, onColorblindToggle }) {
  const svgRef = useRef(null);
  const groupRef = useRef(null);
  const zoomBehaviorRef = useRef(null);
  const [buildings, setBuildings] = useState([]);
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeBuilding, setActiveBuilding] = useState(null);
  const [activePoint, setActivePoint] = useState(null);
  const [selectedEmployerId, setSelectedEmployerId] = useState(null);
  const [hoveredEmployerId, setHoveredEmployerId] = useState(null);
  const [internalColorblindMode, setInternalColorblindMode] = useState(false);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [zoomLevel, setZoomLevel] = useState(1);
  const navigate = useNavigate();

  // Color palettes for edge direction
  const colorPalettes = {
    normal: {
      incoming: '#22c55e', // green
      outgoing: '#ef4444', // red
    },
    colorblind: {
      incoming: '#0ea5e9', // blue
      outgoing: '#f97316', // orange
    },
  };
  const colorblindMode = colorblindModeProp !== undefined ? colorblindModeProp : internalColorblindMode;
  const palette = colorblindMode ? colorPalettes.colorblind : colorPalettes.normal;

  const toggleColorblind = () => {
    if (onColorblindToggle) onColorblindToggle(!colorblindMode);
    else setInternalColorblindMode(!internalColorblindMode);
  };

  // Get edge color based on direction relative to selected employer
  const getEdgeColor = (link, selectedId) => {
    if (!selectedId) return '#999';
    if (link.source === selectedId) return palette.outgoing; // edge going out
    if (link.target === selectedId) return palette.incoming; // edge coming in
    return '#999';
  };

  // Detect if there's a bidirectional edge
  const hasBidirectionalEdge = (links, source, target) => {
    return links.some(l => l.source === target && l.target === source);
  };

  // Generate curved path for bidirectional edges
  const getCurvedPath = (x1, y1, x2, y2, isCurveUp = true) => {
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const curveAmount = distance * 0.15 * (isCurveUp ? 1 : -1);
    const perpX = -dy / distance * curveAmount;
    const perpY = dx / distance * curveAmount;
    const controlX = midX + perpX;
    const controlY = midY + perpY;
    return `M ${x1} ${y1} Q ${controlX} ${controlY} ${x2} ${y2}`;
  };

  // Get health score for employer
  const getHealthScore = (employerId) => {
    const employer = employers.find(e => e.employerId === employerId);
    return employer?.health_score ?? 0.5; // default 0.5 if not found
  };

  // Calculate point radius based on zoom level and health score
  const getPointRadius = (point) => {
    // We want the ON-SCREEN total width (2*radius + stroke) to be constant
    // Compute desired screen width (px) based on prosperity, then convert to data units by dividing with zoom
    if (point.category !== 'Employer') {
      const desiredScreenTotal = 8; // px for non-employers
      const strokeScreen = 1.2; // px desired screen stroke
      const strokeData = strokeScreen / Math.max(zoomLevel, 0.001);
      const radiusData = Math.max(0.6, (desiredScreenTotal / Math.max(zoomLevel, 0.001) - strokeData) / 2);
      return radiusData;
    }

    const healthScore = getHealthScore(parseInt(point.id, 10));
    // Desired on-screen total size in pixels (larger for healthier employers)
    const baseScreen = 8; // px
    const extraPerHealth = 6; // px at health_score=1
    const desiredScreenTotal = baseScreen + (healthScore * extraPerHealth);

    const strokeScreen = 1.2; // desired screen stroke width in px when not hovered
    const strokeData = strokeScreen / Math.max(zoomLevel, 0.001);

    const radiusData = (desiredScreenTotal / Math.max(zoomLevel, 0.001) - strokeData) / 2;
    // clamp to sensible bounds in data units
    return Math.max(0.8, Math.min(40, radiusData));
  };

  const [enabledTypes, setEnabledTypes] = useState({
    Commercial: true,
    Residental: true,
    School: true,
  });
  const [enabledCategories, setEnabledCategories] = useState({
    Employer: true,
    Restaurant: isEmploymentNetworkMap ? false : true,
    Pub: isEmploymentNetworkMap ? false : true,
    School: isEmploymentNetworkMap ? false : true,
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
    // () => buildings.filter((building) => enabledTypes[building.type]),
    () => buildings,
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
  const typeColors = isEmploymentNetworkMap ? {
    Commercial: '#9ca3af',
    Residental: '#9ca3af',
    School: '#9ca3af',
  } : {
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

      {!hideFilters && (
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
      )}

      {loading && <p>Loading building data...</p>}
      {error && <p>{error}</p>}

      {!loading && !error && (
        <div className="chart-wrap" style={{ position: 'relative', marginBottom: '1rem', width: '100%', height: '1000px', overflow: 'hidden' }}>
          <style>{PIN_STYLES}</style>
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
            </button>            {isEmploymentNetworkMap && (
              <button
                type="button"
                className={`map-chip${colorblindMode ? ' active' : ''}`}
                onClick={() => toggleColorblind()}
                title="Toggle colorblind mode"
              >
                {colorblindMode ? '👁️ Normal' : '🎨 Colorblind'}
              </button>
            )}            <button
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
              {/* <image href="/assets/basemap.png" x="0" y="0" width={displayWidth} height={displayHeight} style={{ pointerEvents: 'all' }} /> */}
              
              {/* Network layer - job transitions (if data provided) */}
              {transitionData && transitionData.links && transitionData.links.map((link, idx) => {
                const sourceNode = transitionData.nodes.find(n => n.id === link.source);
                const targetNode = transitionData.nodes.find(n => n.id === link.target);
                
                if (!sourceNode || !targetNode) return null;
                
                const selectedIdNum = selectedEmployerId ? parseInt(selectedEmployerId, 10) : null;
                const hoveredIdNum = hoveredEmployerId ? parseInt(hoveredEmployerId, 10) : null;
                
                const isSelected = selectedIdNum && (link.source === selectedIdNum || link.target === selectedIdNum);
                const isHovered = hoveredIdNum && (link.source === hoveredIdNum || link.target === hoveredIdNum);
                
                let opacity = 0;
                if (isHovered) opacity = 0.8;
                else if (isSelected) opacity = 0.6;
                else if (!selectedIdNum && !hoveredIdNum) opacity = 0.15;
                
                const strokeWidth = Math.max(1, Math.sqrt(link.value) * 2);
                const edgeColor = selectedIdNum ? getEdgeColor(link, selectedIdNum) : '#999';
                
                // Check for bidirectional edge
                const bidirectional = hasBidirectionalEdge(transitionData.links, link.source, link.target);
                const x1 = x(sourceNode.x);
                const y1 = y(sourceNode.y);
                const x2 = x(targetNode.x);
                const y2 = y(targetNode.y);
                
                // For bidirectional edges, curve them in opposite directions
                const isCurveUp = link.source < link.target;
                const pathData = bidirectional ? getCurvedPath(x1, y1, x2, y2, isCurveUp) : `M ${x1} ${y1} L ${x2} ${y2}`;
                
                return (
                  <path
                    key={`transition-${idx}`}
                    d={pathData}
                    stroke={edgeColor}
                    strokeWidth={strokeWidth}
                    fill="none"
                    opacity={opacity}
                    style={{ pointerEvents: 'none', transition: 'opacity 0.15s ease, stroke 0.15s ease' }}
                  />
                );
              })}

              {/* Connection labels - show count on hover */}
              {(selectedEmployerId || hoveredEmployerId) && transitionData && transitionData.links && transitionData.links.map((link, idx) => {
                const selectedIdNum = selectedEmployerId ? parseInt(selectedEmployerId, 10) : null;
                const hoveredIdNum = hoveredEmployerId ? parseInt(hoveredEmployerId, 10) : null;
                const activeId = selectedIdNum || hoveredIdNum;
                
                if (link.source !== activeId && link.target !== activeId) return null;
                
                const sourceNode = transitionData.nodes.find(n => n.id === link.source);
                const targetNode = transitionData.nodes.find(n => n.id === link.target);
                
                if (!sourceNode || !targetNode) return null;
                
                const midX = (x(sourceNode.x) + x(targetNode.x)) / 2;
                const midY = (y(sourceNode.y) + y(targetNode.y)) / 2;
                
                return (
                  <text
                    key={`label-${idx}`}
                    x={midX}
                    y={midY}
                    textAnchor="middle"
                    dy="0.3em"
                    fontSize="11"
                    fill="#333"
                    fontWeight="bold"
                    background="white"
                    style={{ 
                      pointerEvents: 'none',
                      paint: 'white',
                      textShadow: '0 0 3px white, 0 0 3px white',
                      textDecoration: 'none'
                    }}
                  >
                    {link.value}
                  </text>
                );
              })}

              {/* Interactive layer - buildings and points */}
              {filteredBuildings.map((building) => {
                const pathData = building.coords
                  .map((coord, i) => `${i === 0 ? 'M' : 'L'} ${x(coord[0])} ${y(coord[1])}`)
                  .join(' ');
                const isActive = activeBuilding?.id === building.id;
                const isEnabled = !!enabledTypes[building.type];
                return (
                  <path
                    key={`building-${building.id}`}
                    d={pathData}
                    fill={typeColors[building.type]}
                    className={isEnabled ? undefined : 'building-deactivated'}
                    stroke={isActive ? '#ffffff' : '#1f2937'}
                    strokeWidth={isActive ? '2' : '0.8'}
                    opacity={isActive ? 0.9 : 0.6}
                    style={{ cursor: isEnabled ? 'pointer' : 'default', transition: 'all 0.2s ease', pointerEvents: 'auto' }}
                    onMouseEnter={() => { if (isEnabled) setActiveBuilding(building); }}
                    onMouseMove={(e) => {
                      if (!isEnabled) return;
                      const rect = e.currentTarget.closest('.chart-wrap').getBoundingClientRect();
                      setTooltipPos({
                        x: e.clientX - rect.left + 10,
                        y: e.clientY - rect.top + 10,
                      });
                    }}
                    onMouseLeave={() => { if (isEnabled) setActiveBuilding(null); }}
                  />
                );
              })}

              {filteredPoints.map((point) => {
                const baseRadius = getPointRadius(point);
                const isActive = activePoint?.id === point.id && activePoint?.category === point.category;
                const isHoveredOrSelected = hoveredEmployerId === point.id || selectedEmployerId === point.id;
                const displayRadius = isActive ? baseRadius + 2 : isHoveredOrSelected ? baseRadius + 1 : baseRadius;
                
                return (
                <circle
                  key={`${point.category}-${point.id}`}
                  cx={x(point.x)}
                  cy={y(point.y)}
                  r={displayRadius}
                  fill={CATEGORY_COLORS[point.category]}
                  fillOpacity={isHoveredOrSelected ? 1 : 0.88}
                  stroke={isHoveredOrSelected ? '#333' : CATEGORY_COLORS[point.category]}
                  strokeWidth={3}
                  style={{ cursor: 'pointer', pointerEvents: 'auto', transition: 'all 0.15s ease' }}
                  onMouseEnter={() => {
                    if (point.category === 'Employer') {
                      setHoveredEmployerId(point.id);
                    }
                    setActivePoint(point);
                  }}
                  onMouseMove={(e) => {
                    const rect = e.currentTarget.closest('.chart-wrap').getBoundingClientRect();
                    setTooltipPos({
                      x: e.clientX - rect.left + 10,
                      y: e.clientY - rect.top + 10,
                    });
                  }}
                  onMouseLeave={() => {
                    setHoveredEmployerId(null);
                    setActivePoint(null);
                  }}
                  onClick={() => {
                    if (point.category === 'Employer') {
                      setSelectedEmployerId(point.id);
                      if (onEmployerSelect) {
                        onEmployerSelect(point);
                      }
                    }
                  }}
                />
                );
              })}

              {/* Animated pin for selected employer */}
              {selectedEmployerId && filteredPoints.map((point) => {
                if (point.id !== selectedEmployerId || point.category !== 'Employer') return null;
                return (
                  <g key={`pin-${point.id}`}>
                    {/* Pulsing ring */}
                    <circle
                      cx={x(point.x)}
                      cy={y(point.y)}
                      r={6}
                      fill="none"
                      stroke={palette.incoming}
                      strokeWidth={3}
                      className="selected-pin-pulse"
                      style={{ pointerEvents: 'none' }}
                    />
                    {/* Center indicator dot - keep same color as employer point */}
                    <circle
                      cx={x(point.x)}
                      cy={y(point.y)}
                      r={3}
                      fill={CATEGORY_COLORS['Employer']}
                      className="selected-pin-center"
                      style={{ pointerEvents: 'none' }}
                    />
                  </g>
                );
              })}
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
                pointerEvents: 'auto',
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
                  {activePoint.category === 'Employer' && (
                    <div style={{ marginTop: '0.4rem' }}>
                      <button
                        type="button"
                        className="map-chip active"
                        onClick={() => navigate(`/employer/${activePoint.id}`)}
                        title="Open employer details"
                        style={{ pointerEvents: 'auto' }}
                      >
                        View details
                      </button>
                    </div>
                  )}
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