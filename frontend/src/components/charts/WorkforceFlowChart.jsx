import * as d3 from 'd3';
import { useState } from 'react';

const SECTOR_COLORS = {
  'Manufacturing':   '#2563eb',
  'Technology':      '#8b5cf6',
  'Retail':          '#f59e0b',
  'Food & Beverage': '#dc2626',
  'Education':       '#16a34a',
};

function WorkforceFlowChart({ data, title }) {
  const [activeFlow, setActiveFlow] = useState(null);

  const { sectors, transitions } = data;

  const width = 560;
  const nodeWidth = 120;
  const nodeHeight = 28;
  const marginTop = 20;
  const marginBottom = 20;
  const gap = (400 - marginTop - marginBottom - sectors.length * nodeHeight) / (sectors.length - 1);
  const height = marginTop + sectors.length * nodeHeight + (sectors.length - 1) * gap + marginBottom;

  const leftX = 10;
  const rightX = width - nodeWidth - 10;
  const curveStart = leftX + nodeWidth + 4;
  const curveEnd = rightX - 4;

  const nodeY = {};
  sectors.forEach((sector, i) => {
    nodeY[sector] = marginTop + i * (nodeHeight + gap);
  });

  const maxCount = d3.max(transitions, (t) => t.count) ?? 1;
  const strokeScale = d3.scaleLinear().domain([0, maxCount]).range([1.5, 10]);

  return (
    <article className="card">
      <h2 className="chart-title">{title}</h2>
      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '0.5rem', fontSize: 11 }}>
        {sectors.map((s) => (
          <span key={s} style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#374151' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, background: SECTOR_COLORS[s], borderRadius: 2 }} />
            {s}
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#9ca3af', marginBottom: '0.25rem', paddingLeft: leftX, paddingRight: 10 }}>
        <span>From</span>
        <span>To</span>
      </div>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label={title}>
          {transitions.map((t, i) => {
            const y1 = nodeY[t.from] + nodeHeight / 2;
            const y2 = nodeY[t.to] + nodeHeight / 2;
            const mid = (curveStart + curveEnd) / 2;
            const isActive = activeFlow === i;
            return (
              <path
                key={i}
                d={`M ${curveStart} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${curveEnd} ${y2}`}
                fill="none"
                stroke={SECTOR_COLORS[t.from]}
                strokeWidth={strokeScale(t.count)}
                opacity={activeFlow !== null ? (isActive ? 0.9 : 0.15) : 0.45}
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setActiveFlow(i)}
                onMouseLeave={() => setActiveFlow(null)}
              />
            );
          })}

          {sectors.map((sector) => (
            <g key={`left-${sector}`}>
              <rect x={leftX} y={nodeY[sector]} width={nodeWidth} height={nodeHeight} fill={SECTOR_COLORS[sector]} rx="4" opacity={0.85} />
              <text x={leftX + nodeWidth / 2} y={nodeY[sector] + nodeHeight / 2 + 4} textAnchor="middle" fontSize="11" fill="#ffffff" fontWeight="600">
                {sector}
              </text>
            </g>
          ))}

          {sectors.map((sector) => (
            <g key={`right-${sector}`}>
              <rect x={rightX} y={nodeY[sector]} width={nodeWidth} height={nodeHeight} fill={SECTOR_COLORS[sector]} rx="4" opacity={0.85} />
              <text x={rightX + nodeWidth / 2} y={nodeY[sector] + nodeHeight / 2 + 4} textAnchor="middle" fontSize="11" fill="#ffffff" fontWeight="600">
                {sector}
              </text>
            </g>
          ))}
        </svg>

        {activeFlow !== null && (
          <div className="chart-tooltip" role="status">
            <strong>{transitions[activeFlow].from}</strong>
            <span>→ {transitions[activeFlow].to}</span>
            <span>{transitions[activeFlow].count} workers</span>
          </div>
        )}
      </div>
    </article>
  );
}

export default WorkforceFlowChart;
