import * as d3 from 'd3';
import { useState } from 'react';

function HorizontalBarChart({ data, title, valueFormat = (v) => v.toLocaleString(), colorByGrowth = false, selected = null, onSelect = null }) {
  const [activeBar, setActiveBar] = useState(null);

  const width = 560;
  const labelWidth = 150;
  const barAreaWidth = 340;
  const marginTop = 20;
  const rowHeight = 44;
  const height = marginTop + data.length * rowHeight + 8;

  const xMax = d3.max(data, (d) => d.value) ?? 0;
  const x = d3.scaleLinear().domain([0, xMax]).nice().range([0, barAreaWidth]);
  const xTicks = x.ticks(4);

  return (
    <article className="card">
      <h2 className="chart-title">{title}</h2>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label={title}>
          {xTicks.map((tick) => (
            <g key={tick} transform={`translate(${labelWidth + x(tick)}, 0)`}>
              <line y1={marginTop} y2={height - 8} stroke="#e5e7eb" strokeDasharray="3 3" />
              <text y={marginTop - 4} textAnchor="middle" fontSize="10" fill="#9ca3af">
                {tick >= 1000 ? `${(tick / 1000).toFixed(0)}k` : tick}
              </text>
            </g>
          ))}
          {data.map((bar, i) => {
            const y = marginTop + i * rowHeight;
            const isActive = activeBar?.label === bar.label;
            const isSelected = selected === bar.label;
            const barColor = colorByGrowth && bar.growth !== undefined
              ? (bar.growth >= 0 ? '#16a34a' : '#dc2626')
              : (isActive ? '#0e7490' : '#0891b2');
            const dimmed = selected && !isSelected;
            return (
              <g
                key={bar.label}
                onMouseEnter={() => setActiveBar(bar)}
                onMouseLeave={() => setActiveBar(null)}
                onClick={() => onSelect?.(bar.label)}
                style={{ cursor: onSelect ? 'pointer' : 'default' }}
              >
                <text x={labelWidth - 6} y={y + rowHeight / 2 + 4} textAnchor="end" fontSize="11" fill={dimmed ? '#d1d5db' : '#374151'} fontWeight={isSelected ? '700' : '400'}>
                  {bar.label}
                </text>
                <rect
                  x={labelWidth}
                  y={y + 4}
                  width={x(bar.value)}
                  height={rowHeight - 8}
                  fill={barColor}
                  rx="3"
                  opacity={dimmed ? 0.2 : (activeBar && !isActive ? 0.55 : 1)}
                  stroke={isSelected ? '#1f2937' : 'none'}
                  strokeWidth="1.5"
                />
                <text x={labelWidth + x(bar.value) + 4} y={y + rowHeight / 2 + 4} fontSize="11" fill="#374151">
                  {valueFormat(bar.value)}
                </text>
              </g>
            );
          })}
        </svg>
        {activeBar && (
          <div className="chart-tooltip" role="status">
            <strong>{activeBar.label}</strong>
            <span>{valueFormat(activeBar.value)}</span>
            {activeBar.growth !== undefined && (
              <span style={{ color: activeBar.growth >= 0 ? '#16a34a' : '#dc2626' }}>
                {activeBar.growth >= 0 ? '+' : ''}{activeBar.growth}% YoY
              </span>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

export default HorizontalBarChart;
