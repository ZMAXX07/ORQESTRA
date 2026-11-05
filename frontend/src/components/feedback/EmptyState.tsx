import React from 'react';
import { LayersIcon } from '../icons/Icons';
import './Feedback.css';

export interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon = <LayersIcon size={32} />,
  action,
}) => {
  return (
    <div className="orq-empty-state">
      <div className="orq-empty-icon" aria-hidden="true">
        {icon}
      </div>
      <h4 className="orq-empty-title">{title}</h4>
      <p className="orq-empty-description">{description}</p>
      {action && <div className="orq-empty-action">{action}</div>}
    </div>
  );
};
