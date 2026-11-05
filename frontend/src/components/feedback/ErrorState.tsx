import React from 'react';
import { AlertCircleIcon, RefreshIcon } from '../icons/Icons';
import { Button } from '../common/Button';
import './Feedback.css';

export interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  isRetrying?: boolean;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'System Connection Error',
  message,
  onRetry,
  isRetrying = false,
}) => {
  return (
    <div className="orq-error-state" role="alert">
      <div className="orq-error-icon" aria-hidden="true">
        <AlertCircleIcon size={32} />
      </div>
      <div className="orq-error-details">
        <h4 className="orq-error-title">{title}</h4>
        <p className="orq-error-message">{message}</p>
      </div>
      {onRetry && (
        <div className="orq-error-action">
          <Button
            variant="secondary"
            size="sm"
            onClick={onRetry}
            isLoading={isRetrying}
          >
            <RefreshIcon size={14} />
            <span>Retry Check</span>
          </Button>
        </div>
      )}
    </div>
  );
};
