import React from 'react';

/**
 * Tooltip component for providing contextual help
 * @param {Object} props
 * @param {string} props.content - The tooltip text content
 * @param {string} props.position - Position of tooltip (top, bottom, left, right)
 */
function Tooltip({ content, position = 'top' }) {
  return (
    <span className="info-tooltip">
      ?
      <span className={`info-tooltip-content tooltip-${position}`}>
        {content}
      </span>
    </span>
  );
}

export default Tooltip;
