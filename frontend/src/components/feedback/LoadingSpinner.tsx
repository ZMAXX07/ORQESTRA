import React from 'react';
import './Feedback.css';

export interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Loading system status...',
  size = 'md',
}) => {
  return (
    <div className={`orq-spinner-container orq-spinner--${size}`} role="status">
      <div className="orq-spinner-graphic" aria-hidden="true" />
      <span className="orq-spinner-label">{label}</span>
    </div>
  );
};
