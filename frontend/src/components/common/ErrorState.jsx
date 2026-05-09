import React from 'react';

function ErrorState({ 
  message = 'Something went wrong', 
  details = null,
  onRetry = null,
  showRetry = true 
}) {
  return (
    <div className="error-container">
      <div className="error-icon">⚠️</div>
      <h3 className="error-title">Error</h3>
      <p className="error-message">{message}</p>
      {details && (
        <details className="error-details">
          <summary>Technical details</summary>
          <pre>{details}</pre>
        </details>
      )}
      {showRetry && onRetry && (
        <button className="retry-button" onClick={onRetry}>
          <span>🔄</span> Retry
        </button>
      )}
    </div>
  );
}

export default ErrorState;
