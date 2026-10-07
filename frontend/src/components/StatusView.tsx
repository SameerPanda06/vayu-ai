import React from 'react';

interface StatusViewProps {
  type: 'loading' | 'error' | 'empty';
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export const StatusView: React.FC<StatusViewProps> = ({
  type,
  title,
  message,
  onRetry,
}) => {
  if (type === 'loading') {
    return (
      <div className="status-container status-loading" role="status">
        <div className="spinner" aria-hidden="true"></div>
        <h3 className="status-title">{title || 'Loading Forecast Data...'}</h3>
        <p className="status-message">
          {message || 'Connecting to Vayu AI backend to retrieve 72-hour forecast stream.'}
        </p>
      </div>
    );
  }

  if (type === 'error') {
    return (
      <div className="status-container status-error-box" role="alert">
        <div className="status-icon-error">⚠️</div>
        <h3 className="status-title">{title || 'Data Retrieval Error'}</h3>
        <p className="status-message">
          {message || 'Unable to connect to Vayu AI backend. Ensure the FastAPI service is running.'}
        </p>
        {onRetry && (
          <button type="button" className="retry-btn" onClick={onRetry}>
            🔄 Retry Connection
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="status-container status-empty" role="status">
      <div className="status-icon-empty">📊</div>
      <h3 className="status-title">{title || 'No Forecast Data Available'}</h3>
      <p className="status-message">
        {message || 'Select a valid monitoring station above to view synthetic forecast trajectories.'}
      </p>
    </div>
  );
};
