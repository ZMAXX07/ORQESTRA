import React from 'react';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { MenuIcon, XIcon } from '../icons/Icons';
import { useAuth } from '../../context/AuthContext';
import { RealtimeStatusBadge } from '../realtime/RealtimeStatusBadge';
import './Navigation.css';

export interface HeaderProps {
  isBackendHealthy: boolean | null;
  environmentName?: string;
  onOpenSignIn?: () => void;
  onOpenStatus?: () => void;
  isMobileMenuOpen?: boolean;
  onToggleMobileMenu?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  isBackendHealthy,
  onOpenSignIn,
  onOpenStatus,
  isMobileMenuOpen = false,
  onToggleMobileMenu,
}) => {
  const { user, signOut, isConfigured, serverAuth, switchBusiness } = useAuth();

  return (
    <header className="orq-header" role="banner">
      <div className="orq-header-container">
        <div className="orq-header-left">
          {onToggleMobileMenu && (
            <button
              type="button"
              className="orq-header-menu-toggle"
              aria-label={isMobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={isMobileMenuOpen}
              aria-controls="orq-main-navigation"
              onClick={onToggleMobileMenu}
            >
              {isMobileMenuOpen ? <XIcon size={20} /> : <MenuIcon size={20} />}
            </button>
          )}

          <div className="orq-brand">
            <img
              src="/orqestra-icon.png"
              alt="Orqestra"
              className="orq-brand-logo"
              width="36"
              height="36"
            />
            <div className="orq-brand-text">
              <span className="orq-brand-name">Orqestra</span>
              <span className="orq-brand-tagline">Operations Platform</span>
            </div>
          </div>
        </div>

        <div className="orq-header-meta">
          <div className="orq-header-status-group">
            {isBackendHealthy === false && (
              onOpenStatus ? (
                <button
                  type="button"
                  className="orq-header-status-btn"
                  onClick={onOpenStatus}
                  aria-label="Backend offline. View system status and diagnostics"
                  title="Backend service offline. Click to view System Status & Diagnostics"
                >
                  <Badge variant="degraded">
                    <span className="orq-badge-text-full">Backend Offline</span>
                    <span className="orq-badge-text-short">Offline</span>
                  </Badge>
                </button>
              ) : (
                <Badge variant="degraded">
                  <span className="orq-badge-text-full">Backend Offline</span>
                  <span className="orq-badge-text-short">Offline</span>
                </Badge>
              )
            )}

            <RealtimeStatusBadge />
          </div>

          {user && serverAuth?.memberships && serverAuth.memberships.length > 0 && (
            <div className="orq-header-workspace-select-wrapper">
              <select
                className="orq-header-workspace-select"
                value={serverAuth.active_business?.business_id || ''}
                onChange={(e) => switchBusiness?.(e.target.value)}
                aria-label="Select Business Workspace"
                title="Active Business Workspace"
                data-testid="workspace-select"
              >
                {serverAuth.memberships.map((m) => (
                  <option key={m.business_id} value={m.business_id}>
                    {m.business_name} ({m.currency})
                  </option>
                ))}
              </select>
            </div>
          )}

          {user ? (
            <div className="orq-header-user">
              <div className="orq-header-avatar" aria-hidden="true">
                {user.email ? user.email.slice(0, 2).toUpperCase() : 'OP'}
              </div>
              <div className="orq-header-user-text">
                <span className="orq-header-email" title={user.email ?? ''}>
                  {user.email ?? 'Authenticated Operator'}
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => signOut()}
                className="orq-header-auth-btn"
              >
                Sign Out
              </Button>
            </div>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={onOpenSignIn}
              className="orq-header-auth-btn"
              title={isConfigured ? 'Sign in to Orqestra' : 'Supabase credentials not configured'}
            >
              Sign In
            </Button>
          )}
        </div>
      </div>
    </header>
  );
};

