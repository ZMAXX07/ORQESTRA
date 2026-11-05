import React from 'react';
import { AlertCircleIcon, AlertTriangleIcon, CheckIcon, InfoIcon } from '../icons/Icons';
import './Alert.css';

export type AlertType = 'info' | 'warning' | 'error' | 'success';

export interface AlertProps {
  type?: AlertType;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export const Alert: React.FC<AlertProps> = ({
  type = 'info',
  title,
  children,
  className = '',
}) => {
  const getIcon = () => {
    switch (type) {
      case 'success':
        return <CheckIcon size={18} />;
      case 'warning':
        return <AlertTriangleIcon size={18} />;
      case 'error':
        return <AlertCircleIcon size={18} />;
      case 'info':
      default:
        return <InfoIcon size={18} />;
    }
  };

  return (
    <div
      role={type === 'error' ? 'alert' : 'status'}
      className={`orq-alert orq-alert--${type} ${className}`}
    >
      <div className="orq-alert-icon">{getIcon()}</div>
      <div className="orq-alert-body">
        {title && <div className="orq-alert-title">{title}</div>}
        <div className="orq-alert-content">{children}</div>
      </div>
    </div>
  );
};
