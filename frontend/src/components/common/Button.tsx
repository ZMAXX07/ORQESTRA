import React from 'react';
import './Button.css';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline';
  size?: 'sm' | 'md';
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled,
  className = '',
  ...props
}) => {
  return (
    <button
      className={`orq-button orq-button--${variant} orq-button--${size} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <span className="orq-button-spinner" aria-hidden="true" />}
      <span className="orq-button-content">{children}</span>
    </button>
  );
};
