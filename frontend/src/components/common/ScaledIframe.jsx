import { useState, useEffect, useRef } from 'react';

/**
 * ScaledIframe - An iframe that scales its content to fit without scrolling
 * @param {Object} props
 * @param {string} props.srcDoc - HTML content for the iframe
 * @param {number} props.contentHeight - Expected height of the iframe content (default: 2000)
 */
function ScaledIframe({ srcDoc, contentHeight = 2000 }) {
  const [scale, setScale] = useState(1);
  const containerRef = useRef(null);

  useEffect(() => {
    const updateScale = () => {
      if (containerRef.current) {
        const containerHeight = window.innerHeight - 250; // Account for header and padding
        const calculatedScale = containerHeight / contentHeight;
        setScale(Math.min(calculatedScale, 1)); // Never scale up, only down
      }
    };

    updateScale();
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, [contentHeight]);

  const scaledHeight = contentHeight * scale;

  return (
    <div 
      ref={containerRef}
      style={{ 
        width: '100%', 
        height: `${scaledHeight}px`,
        overflow: 'hidden',
        position: 'relative'
      }}
    >
      <iframe
        srcDoc={srcDoc}
        style={{
          width: `${100 / scale}%`,
          height: `${contentHeight}px`,
          border: 'none',
          transform: `scale(${scale})`,
          transformOrigin: 'top left',
          overflow: 'hidden'
        }}
      />
    </div>
  );
}

export default ScaledIframe;
