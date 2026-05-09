import React from 'react';

/**
 * Loading spinner component
 * @param {Object} props
 * @param {string} props.message - Optional loading message
 */
function LoadingSpinner({ message = 'Loading...' }) {
  return (
    <div className="loading-container">
      <div className="loading-spinner"></div>
      <div className="loading-text">{message}</div>
    </div>
  );
}

export default LoadingSpinner;
