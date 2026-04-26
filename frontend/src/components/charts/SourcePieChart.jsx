import * as d3 from 'd3';
import { useState } from 'react';

const COLORS = ['#6366f1', '#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6'];

function SourcePieChart({ data }) {
  const [activeSource, setActiveSource] = useState(null);

  const width = 560;
  const height = 280;
  const radius = 90;
  const centerX = 170;
  const centerY = 145;

  const pie = d3.pie().value((d) => d.value).sort(null);
  const arc = d3.arc().innerRadius(0).outerRadius(radius);
  const activeArc = d3.arc().innerRadius(0).outerRadius(radius + 8);
  const arcLabel = d3.arc().innerRadius(radius + 14).outerRadius(radius + 14);
  const arcs = pie(data);

  return (
    <article className="card">
      <h2 className="chart-title">Traffic Sources</h2>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label="Traffic source pie chart">
          <g transform={`translate(${centerX},${centerY})`}>
            {arcs.map((slice, index) => (
              <path
                key={slice.data.source}
                d={(activeSource?.source === slice.data.source ? activeArc(slice) : arc(slice)) ?? ''}
                fill={COLORS[index % COLORS.length]}
                stroke="#ffffff"
                strokeWidth="1.5"
                onMouseEnter={() => setActiveSource(slice.data)}
                onMouseLeave={() => setActiveSource(null)}
              />
            ))}

            {arcs.map((slice) => {
              const [x, y] = arcLabel.centroid(slice);
              return (
                <text key={`${slice.data.source}-label`} x={x} y={y} textAnchor="middle" fontSize="10" fill="#374151">
                  {slice.data.value}%
                </text>
              );
            })}
          </g>

          <g transform="translate(330,70)">
            {data.map((entry, index) => (
              <g
                key={entry.source}
                transform={`translate(0, ${index * 24})`}
                onMouseEnter={() => setActiveSource(entry)}
                onMouseLeave={() => setActiveSource(null)}
                className="legend-item"
              >
                <rect width="10" height="10" y="-8" fill={COLORS[index % COLORS.length]} rx="2" />
                <text x="16" y="0" fontSize="12" fill="#374151">
                  {entry.source} ({entry.value}%)
                </text>
              </g>
            ))}
          </g>
        </svg>

        {activeSource && (
          <div className="chart-tooltip" role="status">
            <strong>{activeSource.source}</strong>
            <span>{activeSource.value}% of traffic</span>
          </div>
        )}
      </div>
    </article>
  );
}

export default SourcePieChart;
