import React, { useEffect } from 'react';
import { Badge } from '../common/Badge';
import {
  DashboardIcon,
  ServerIcon,
  PackageIcon,
  LayersIcon,
  UsersIcon,
  ShoppingCartIcon,
  ClockIcon,
  ShieldCheckIcon,
  XIcon,
} from '../icons/Icons';
import './Navigation.css';

interface NavItem {
  id: string;
  label: string;
  available: boolean;
  phaseNotice?: string;
  icon: React.FC<{ size?: number; className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'foundation', label: 'Operations Dashboard', available: true, icon: DashboardIcon },
  { id: 'products', label: 'Products Catalog', available: true, icon: PackageIcon },
  { id: 'inventory', label: 'Inventory Management', available: true, icon: LayersIcon },
  { id: 'customers', label: 'Customer Directory', available: true, icon: UsersIcon },
  { id: 'orders', label: 'Order Processing', available: true, icon: ShoppingCartIcon },
  { id: 'invoices', label: 'Invoices & Billing', available: true, icon: ClockIcon },
  { id: 'ai-ops', label: 'AI Order Extraction', available: true, icon: ShieldCheckIcon },
  { id: 'system-status', label: 'System Status', available: true, icon: ServerIcon },
];

export interface NavigationShellProps {
  activeId?: string;
  onSelect?: (id: string) => void;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
  environmentName?: string;
}

export const NavigationShell: React.FC<NavigationShellProps> = ({
  activeId = 'foundation',
  onSelect,
  isMobileOpen = false,
  onCloseMobile,
}) => {
  // Close mobile drawer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isMobileOpen) {
        onCloseMobile?.();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMobileOpen, onCloseMobile]);

  // Prevent background scrolling while mobile navigation drawer is active
  useEffect(() => {
    if (isMobileOpen) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [isMobileOpen]);

  const handleItemClick = (id: string) => {
    onSelect?.(id);
    onCloseMobile?.();
  };

  return (
    <>
      {isMobileOpen && (
        <div
          className="orq-nav-backdrop"
          onClick={onCloseMobile}
          aria-hidden="true"
          data-testid="nav-backdrop"
        />
      )}
      <nav
        id="orq-main-navigation"
        className={`orq-nav-shell ${isMobileOpen ? 'is-mobile-open' : ''}`}
        aria-label="Main Navigation"
      >
        <div className="orq-nav-mobile-header">
          <div className="orq-nav-mobile-brand">
            <img
              src="/orqestra-icon.png"
              alt="Orqestra"
              className="orq-nav-mobile-logo"
              width="24"
              height="24"
            />
            <span className="orq-nav-mobile-title">Navigation</span>
          </div>
          {onCloseMobile && (
            <button
              type="button"
              className="orq-nav-mobile-close"
              onClick={onCloseMobile}
              aria-label="Close navigation menu"
            >
              <XIcon size={18} />
            </button>
          )}
        </div>

        <div className="orq-nav-section-title">System Modules</div>
        <ul className="orq-nav-list" role="list">
          {NAV_ITEMS.map((item) => {
            const isActive = item.id === activeId;
            const IconComponent = item.icon;
            return (
              <li key={item.id} className="orq-nav-list-item">
                <button
                  type="button"
                  className={`orq-nav-button ${isActive ? 'is-active' : ''} ${!item.available ? 'is-disabled' : ''}`}
                  disabled={!item.available}
                  aria-disabled={!item.available}
                  aria-current={isActive ? 'page' : undefined}
                  onClick={() => item.available && handleItemClick(item.id)}
                >
                  <span className="orq-nav-icon">
                    <IconComponent size={16} />
                  </span>
                  <span className="orq-nav-label">{item.label}</span>
                  {!item.available && item.phaseNotice && (
                    <Badge variant="not_connected" className="orq-nav-badge">
                      {item.phaseNotice}
                    </Badge>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
};

