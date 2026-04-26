import * as d3 from 'd3';
import { useState } from 'react';

function LineTrendChart({ data }) {
  const [activePoint, setActivePoint] = useState(null);

  const width = 560;
  const height = 280;
  const margin = { top: 12, right: 16, bottom: 36, left: 44 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const x = d3
    .scalePoint()
    .domain(data.map((d) => d.date))
    .range([0, innerWidth]);

  const yMax = d3.max(data, (d) => d.visits) ?? 0;
  const y = d3.scaleLinear().domain([0, yMax]).nice().range([innerHeight, 0]);

  const line = d3
    .line()
    .x((d) => x(d.date))
    .y((d) => y(d.visits))
    .curve(d3.curveMonotoneX);

  const yTicks = y.ticks(5);

  return (
    <article className="card">
      <h2 className="chart-title">Traffic Trend</h2>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label="Traffic trend line chart">
          <g transform={`translate(${margin.left},${margin.top})`}>
            {yTicks.map((tick) => (
              <g key={tick} transform={`translate(0,${y(tick)})`}>
                <line x1={0} x2={innerWidth} stroke="#e5e7eb" strokeDasharray="3 3" />
                <text x={-8} y={4} textAnchor="end" fontSize="11" fill="#6b7280">
                  {tick}
                </text>
              </g>
            ))}

            {data.map((point) => (
              <text
                key={point.date}
                x={x(point.date)}
                y={innerHeight + 18}
                textAnchor="middle"
                fontSize="11"
                fill="#6b7280"
              >
                {point.date}
              </text>
            ))}

            <path d={line(data) ?? ''} fill="none" stroke="#2563eb" strokeWidth="2.5" />

            {data.map((point) => (
              <g key={`${point.date}-dot`}>
                <circle
                  cx={x(point.date)}
                  cy={y(point.visits)}
                  r={activePoint?.date === point.date ? 5 : 3}
                  fill="#2563eb"
                />
                <circle
                  cx={x(point.date)}
                  cy={y(point.visits)}
                  r="12"
                  fill="transparent"
                  onMouseEnter={() => setActivePoint(point)}
                  onMouseLeave={() => setActivePoint(null)}
                />
              </g>
            ))}
          </g>
        </svg>

        {activePoint && (
          <div className="chart-tooltip" role="status">
            <strong>{activePoint.date}</strong>
            <span>{activePoint.visits.toLocaleString()} visits</span>
          </div>
        )}
      </div>
    </article>
  );
}

export default LineTrendChart;
