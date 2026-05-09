import { useState, useRef, useEffect } from 'react';

/**
 * An iframe that automatically adjusts its height to fit its content
 */
function AutoResizingIframe({ srcDoc, title, className, style = {} }) {
  const iframeRef = useRef(null);
  const [height, setHeight] = useState('800px'); // Default starting height

  const handleLoad = () => {
    if (iframeRef.current && iframeRef.current.contentWindow) {
      try {
        const doc = iframeRef.current.contentDocument || iframeRef.current.contentWindow.document;
        if (doc) {
          // Add a small buffer to prevent scrollbars
          const newHeight = doc.documentElement.scrollHeight + 20;
          setHeight(`${newHeight}px`);
        }
      } catch (e) {
        console.error('Could not resize iframe:', e);
        // Fallback to a large but not insane height
        setHeight('1500px');
      }
    }
  };

  // Re-calculate on srcDoc change
  useEffect(() => {
    // Initial delay to allow internal D3 transitions to finish
    const timer = setTimeout(handleLoad, 500);
    return () => clearTimeout(timer);
  }, [srcDoc]);

  return (
    <iframe
      ref={iframeRef}
      srcDoc={srcDoc}
      title={title}
      className={className}
      onLoad={handleLoad}
      style={{
        ...style,
        width: '100%',
        height: height,
        border: 'none',
        transition: 'height 0.3s ease'
      }}
    />
  );
}

export default AutoResizingIframe;
