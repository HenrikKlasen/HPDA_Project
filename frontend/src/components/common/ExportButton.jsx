import { useState, useRef, useEffect } from 'react';
import { exportToPNG, exportToSVG, exportToCSV, exportToJSON } from '../../utils/exportUtils';

/**
 * ExportButton component with dropdown menu for different export formats
 * @param {Object} props
 * @param {HTMLElement|string} props.targetRef - Reference to element to export or selector string
 * @param {Array} props.data - Optional data array for CSV/JSON export
 * @param {string} props.filename - Base filename (without extension)
 */
function ExportButton({ targetRef, data, filename = 'export' }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleExport = (format) => {
    let element = targetRef;
    
    // If targetRef is a string selector, find the element
    if (typeof targetRef === 'string') {
      element = document.querySelector(targetRef);
    } else if (targetRef?.current) {
      element = targetRef.current;
    }

    switch (format) {
      case 'png':
        if (element) {
          const svg = element.tagName === 'svg' ? element : element.querySelector('svg');
          if (svg) {
            exportToPNG(svg, `${filename}.png`);
          } else {
            alert('No SVG element found to export');
          }
        }
        break;
      case 'svg':
        if (element) {
          const svg = element.tagName === 'svg' ? element : element.querySelector('svg');
          if (svg) {
            exportToSVG(svg, `${filename}.svg`);
          } else {
            alert('No SVG element found to export');
          }
        }
        break;
      case 'csv':
        if (data && data.length > 0) {
          exportToCSV(data, `${filename}.csv`);
        } else {
          alert('No data available to export');
        }
        break;
      case 'json':
        if (data) {
          exportToJSON(data, `${filename}.json`);
        } else {
          alert('No data available to export');
        }
        break;
      default:
        break;
    }

    setIsOpen(false);
  };

  return (
    <div className="export-button-container" ref={dropdownRef}>
      <button
        className="export-button"
        onClick={() => setIsOpen(!isOpen)}
        title="Export chart or data"
      >
        <span className="export-icon">📥</span>
        <span>Export</span>
        <span className="export-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className="export-dropdown">
          <button onClick={() => handleExport('png')} className="export-option">
            <span className="export-option-icon">🖼️</span>
            <div className="export-option-text">
              <div className="export-option-label">Export as PNG</div>
              <div className="export-option-desc">High-quality image</div>
            </div>
          </button>
          <button onClick={() => handleExport('svg')} className="export-option">
            <span className="export-option-icon">📐</span>
            <div className="export-option-text">
              <div className="export-option-label">Export as SVG</div>
              <div className="export-option-desc">Vector graphics</div>
            </div>
          </button>
          {data && (
            <>
              <div className="export-divider" />
              <button onClick={() => handleExport('csv')} className="export-option">
                <span className="export-option-icon">📊</span>
                <div className="export-option-text">
                  <div className="export-option-label">Export as CSV</div>
                  <div className="export-option-desc">Spreadsheet data</div>
                </div>
              </button>
              <button onClick={() => handleExport('json')} className="export-option">
                <span className="export-option-icon">📄</span>
                <div className="export-option-text">
                  <div className="export-option-label">Export as JSON</div>
                  <div className="export-option-desc">Raw data format</div>
                </div>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default ExportButton;
