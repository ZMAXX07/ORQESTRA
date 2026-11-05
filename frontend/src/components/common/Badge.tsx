import React from 'react';
import './Badge.css';

export type BadgeVariant =
  | 'operational'
  | 'degraded'
  | 'not_connected'
  | 'connected'
  | 'not_configured'
  | 'unavailable'
  | 'error'
  | 'neutral'
  | 'info';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  children,
  className = '',
  ...props
}) => {
  return (
    <span className={`orq-badge orq-badge--${variant} ${className}`} {...props}>
      <span className="orq-badge-dot" aria-hidden="true" />
      {children}
    </span>
  );
};
