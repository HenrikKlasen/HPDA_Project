import * as d3 from 'd3';
import { useState } from 'react';

function GroupedBarChart({ data, title, labelA, labelB, colorA = '#2563eb', colorB = '#dc2626' }) {
  const [activeItem, setActiveItem] = useState(null);

  const width = 560;
  const height = 280;
  const margin = { top: 24, right: 16, bottom: 40, left: 56 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const groups = data.map((d) => d.group);
  const xGroup = d3.scaleBand().domain(groups).range([0, innerWidth]).padding(0.2);
  const xBar = d3.scaleBand().domain(['a', 'b']).range([0, xGroup.bandwidth()]).padding(0.05);
  const yMax = d3.max(data, (d) => Math.max(d.a, d.b)) ?? 0;
  const y = d3.scaleLinear().domain([0, yMax]).nice().range([innerHeight, 0]);
  const yTicks = y.ticks(5);

  return (
    <article className="card">
      <h2 className="chart-title">{title}</h2>
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
        {[{ label: labelA, color: colorA }, { label: labelB, color: colorB }].map((l) => (
          <span key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#374151' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, background: l.color, borderRadius: 2 }} />
            {l.label}
          </span>
        ))}
      </div>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label={title}>
          <g transform={`translate(${margin.left},${margin.top})`}>
            {yTicks.map((tick) => (
              <g key={tick} transform={`translate(0,${y(tick)})`}>
                <line x1={0} x2={innerWidth} stroke="#e5e7eb" strokeDasharray="3 3" />
                <text x={-8} y={4} textAnchor="end" fontSize="11" fill="#6b7280">
                  {tick >= 1000 ? `${(tick / 1000).toFixed(0)}k` : tick}
                </text>
              </g>
            ))}
            {data.map((d) => (
              <g key={d.group} transform={`translate(${xGroup(d.group)},0)`}>
                <rect
                  x={xBar('a')}
                  y={y(d.a)}
                  width={xBar.bandwidth()}
                  height={innerHeight - y(d.a)}
                  fill={colorA}
                  rx="3"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setActiveItem({ group: d.group, type: labelA, value: d.a })}
                  onMouseLeave={() => setActiveItem(null)}
                />
                <rect
                  x={xBar('b')}
                  y={y(d.b)}
                  width={xBar.bandwidth()}
                  height={innerHeight - y(d.b)}
                  fill={colorB}
                  rx="3"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setActiveItem({ group: d.group, type: labelB, value: d.b })}
                  onMouseLeave={() => setActiveItem(null)}
                />
                <text
                  x={xGroup.bandwidth() / 2}
                  y={innerHeight + 18}
                  textAnchor="middle"
                  fontSize="11"
                  fill="#6b7280"
                >
                  {d.group}
                </text>
              </g>
            ))}
          </g>
        </svg>
        {activeItem && (
          <div className="chart-tooltip" role="status">
            <strong>{activeItem.group}</strong>
            <span>{activeItem.type}: ${activeItem.value.toLocaleString()}</span>
          </div>
        )}
      </div>
    </article>
  );
}

export default GroupedBarChart;
