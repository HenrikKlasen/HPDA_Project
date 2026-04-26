import * as d3 from 'd3';
import { useState } from 'react';

function CategoryBarChart({ data }) {
  const [activeBar, setActiveBar] = useState(null);

  const width = 560;
  const height = 280;
  const margin = { top: 12, right: 16, bottom: 40, left: 44 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const x = d3
    .scaleBand()
    .domain(data.map((d) => d.category))
    .range([0, innerWidth])
    .padding(0.22);

  const yMax = d3.max(data, (d) => d.count) ?? 0;
  const y = d3.scaleLinear().domain([0, yMax]).nice().range([innerHeight, 0]);
  const yTicks = y.ticks(5);

  return (
    <article className="card">
      <h2 className="chart-title">Events by Category</h2>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label="Event categories bar chart">
          <g transform={`translate(${margin.left},${margin.top})`}>
            {yTicks.map((tick) => (
              <g key={tick} transform={`translate(0,${y(tick)})`}>
                <line x1={0} x2={innerWidth} stroke="#e5e7eb" strokeDasharray="3 3" />
                <text x={-8} y={4} textAnchor="end" fontSize="11" fill="#6b7280">
                  {tick}
                </text>
              </g>
            ))}

            {data.map((bar) => (
              <g key={bar.category}>
                <rect
                  x={x(bar.category)}
                  y={y(bar.count)}
                  width={x.bandwidth()}
                  height={innerHeight - y(bar.count)}
                  fill={activeBar?.category === bar.category ? '#0e7490' : '#0891b2'}
                  rx="4"
                  onMouseEnter={() => setActiveBar(bar)}
                  onMouseLeave={() => setActiveBar(null)}
                />
                <text
                  x={(x(bar.category) ?? 0) + x.bandwidth() / 2}
                  y={innerHeight + 18}
                  textAnchor="middle"
                  fontSize="11"
                  fill="#6b7280"
                >
                  {bar.category}
                </text>
              </g>
            ))}
          </g>
        </svg>

        {activeBar && (
          <div className="chart-tooltip" role="status">
            <strong>{activeBar.category}</strong>
            <span>{activeBar.count.toLocaleString()} events</span>
          </div>
        )}
      </div>
    </article>
  );
}

export default CategoryBarChart;
