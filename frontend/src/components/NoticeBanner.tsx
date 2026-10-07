import React from 'react';
import { InfoIcon } from './Icons';

export const NoticeBanner: React.FC = () => {
  return (
    <div className="compact-notice-bar" role="status" aria-label="Demo status notice">
      <div className="compact-notice-content">
        <InfoIcon size={16} className="notice-icon" />
        <span className="notice-text">
          Demo mode · Synthetic data · Not a validated forecast
        </span>
      </div>
    </div>
  );
};
