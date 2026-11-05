import React from 'react';
import { useRealtime } from '../../context/RealtimeContext';
import './RealtimeStatusBadge.css';

export interface RealtimeStatusBadgeProps {
  className?: string;
  showRetry?: boolean;
  showConnected?: boolean;
}

export const RealtimeStatusBadge: React.FC<RealtimeStatusBadgeProps> = ({
  className = '',
  showRetry = true,
  showConnected = false,
}) => {
  const { status, error, reconnect, activeBusinessId } = useRealtime();

  // If connected and showConnected is false (default for normal UI), hide badge completely
  if (status === 'connected' && !showConnected) {
    return null;
  }

  // If no active business context and disconnected, do not show badge
  if (!activeBusinessId && status === 'disconnected') {
    return null;
  }

  if (status === 'connected') {
    return (
      <div
        className={`orq-realtime-badge is-connected ${className}`.trim()}
        role="status"
        aria-live="polite"
        title="Realtime synchronization active"
      >
        <span className="orq-realtime-indicator" aria-hidden="true" />
        <span>Live Sync: Connected</span>
      </div>
    );
  }

  if (status === 'connecting') {
    return (
      <div
        className={`orq-realtime-badge is-connecting ${className}`.trim()}
        role="status"
        aria-live="polite"
        title="Connecting realtime data synchronization..."
      >
        <span className="orq-realtime-indicator" aria-hidden="true" />
        <span>Live Sync: Connecting...</span>
      </div>
    );
  }

  // Disconnected or Error state: subtle, accessible warning with clear explanation and recovery state
  const warningLabel = error ? `Live Sync: ${error}` : 'Live Sync Disconnected';
  const explanation = error || 'Realtime synchronization disconnected. Real-time table updates may be delayed.';

  return (
    <div
      className={`orq-realtime-badge is-warning ${className}`.trim()}
      role="status"
      aria-live="polite"
      title={explanation}
    >
      <span className="orq-realtime-indicator" aria-hidden="true" />
      <span className="orq-realtime-label">{warningLabel}</span>
      {showRetry && (
        <button
          type="button"
          onClick={reconnect}
          className="orq-realtime-retry-btn"
          aria-label="Retry realtime connection"
        >
          Retry
        </button>
      )}
    </div>
  );
};
