import { useState, Children } from 'react';

/**
 * PaginatedContainer - A component that displays children one at a time with navigation arrows
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child elements to paginate through
 * @param {string} props.height - Container height (default: '400px')
 */
function PaginatedContainer({ children, height = '400px' }) {
  const childArray = Children.toArray(children);
  const [currentPage, setCurrentPage] = useState(0);
  const totalPages = childArray.length;

  const handlePrevious = () => {
    setCurrentPage((prev) => (prev > 0 ? prev - 1 : prev));
  };

  const handleNext = () => {
    setCurrentPage((prev) => (prev < totalPages - 1 ? prev + 1 : prev));
  };

  if (totalPages === 0) {
    return null;
  }

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ 
        height, 
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        {childArray[currentPage]}
      </div>
      
      {totalPages > 1 && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '12px',
          marginTop: '12px',
          padding: '8px',
          background: 'var(--card)',
          borderRadius: '8px',
          boxShadow: 'var(--shadow)'
        }}>
          <button
            onClick={handlePrevious}
            disabled={currentPage === 0}
            style={{
              padding: '6px 12px',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              background: currentPage === 0 ? 'var(--bg)' : 'var(--card)',
              color: currentPage === 0 ? 'var(--muted)' : 'var(--text)',
              cursor: currentPage === 0 ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: '600'
            }}
          >
            ←
          </button>
          
          <span style={{
            fontSize: '14px',
            color: 'var(--text)',
            fontWeight: '500',
            minWidth: '50px',
            textAlign: 'center'
          }}>
            {currentPage + 1} / {totalPages}
          </span>
          
          <button
            onClick={handleNext}
            disabled={currentPage === totalPages - 1}
            style={{
              padding: '6px 12px',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              background: currentPage === totalPages - 1 ? 'var(--bg)' : 'var(--card)',
              color: currentPage === totalPages - 1 ? 'var(--muted)' : 'var(--text)',
              cursor: currentPage === totalPages - 1 ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: '600'
            }}
          >
            →
          </button>
        </div>
      )}
    </div>
  );
}

export default PaginatedContainer;
