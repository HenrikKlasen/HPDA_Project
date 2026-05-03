import * as d3 from 'd3';
import { useState } from 'react';

function MultiLineChart({ data, title, highlightName = null, onSelect = null }) {
  const [activePoint, setActivePoint] = useState(null);

  const width = 560;
  const height = 280;
  const margin = { top: 12, right: 16, bottom: 36, left: 56 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const labels = data[0]?.values.map((v) => v.label) ?? [];
  const x = d3.scalePoint().domain(labels).range([0, innerWidth]);
  const yMax = d3.max(data, (s) => d3.max(s.values, (v) => v.value)) ?? 0;
  const y = d3.scaleLinear().domain([0, yMax]).nice().range([innerHeight, 0]);
  const yTicks = y.ticks(5);

  return (
    <article className="card">
      <h2 className="chart-title">{title}</h2>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
        {data.map((s) => (
          <span
            key={s.name}
            onClick={() => onSelect?.(s.name)}
            style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, cursor: onSelect ? 'pointer' : 'default', color: highlightName && highlightName !== s.name ? '#d1d5db' : '#374151', fontWeight: highlightName === s.name ? '700' : '400' }}
          >
            <span style={{ display: 'inline-block', width: 14, height: 3, background: s.color, borderRadius: 2, opacity: highlightName && highlightName !== s.name ? 0.25 : 1 }} />
            {s.name}
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
            {labels.map((label) => (
              <text key={label} x={x(label)} y={innerHeight + 18} textAnchor="middle" fontSize="11" fill="#6b7280">
                {label}
              </text>
            ))}
            {data.map((series) => {
              const line = d3
                .line()
                .x((v) => x(v.label))
                .y((v) => y(v.value))
                .curve(d3.curveMonotoneX);
              const dimmed = highlightName && highlightName !== series.name;
              return (
                <path key={series.name} d={line(series.values) ?? ''} fill="none" stroke={series.color} strokeWidth={highlightName === series.name ? 3 : 2} opacity={dimmed ? 0.15 : 1} />
              );
            })}
            {data.map((series) => {
              const dimmed = highlightName && highlightName !== series.name;
              return series.values.map((point) => (
                <circle
                  key={`${series.name}-${point.label}`}
                  cx={x(point.label)}
                  cy={y(point.value)}
                  r={activePoint?.series === series.name && activePoint?.label === point.label ? 5 : 2.5}
                  fill={series.color}
                  opacity={dimmed ? 0.15 : 1}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setActivePoint({ series: series.name, label: point.label, value: point.value, color: series.color })}
                  onMouseLeave={() => setActivePoint(null)}
                />
              ));
            })}
          </g>
        </svg>
        {activePoint && (
          <div className="chart-tooltip" role="status">
            <strong style={{ color: activePoint.color }}>{activePoint.series}</strong>
            <span>{activePoint.label}: {activePoint.value.toLocaleString()}</span>
          </div>
        )}
      </div>
    </article>
  );
}

export default MultiLineChart;
