import React, { useState } from 'react';
import { Header } from '../components/navigation/Header';
import { NavigationShell } from '../components/navigation/NavigationShell';
import './MainLayout.css';

export interface MainLayoutProps {
  children: React.ReactNode;
  isBackendHealthy: boolean | null;
  environmentName?: string;
  activeNavId?: string;
  onNavSelect?: (id: string) => void;
  onOpenSignIn?: () => void;
  onOpenStatus?: () => void;
  onOpenLegal?: (doc: 'terms' | 'privacy') => void;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  children,
  isBackendHealthy,
  environmentName,
  activeNavId,
  onNavSelect,
  onOpenSignIn,
  onOpenStatus,
  onOpenLegal,
}) => {
  const [isMobileNavOpen, setIsMobileNavOpen] = useState<boolean>(false);

  return (
    <div className="orq-layout-root">
      <Header
        isBackendHealthy={isBackendHealthy}
        environmentName={environmentName}
        onOpenSignIn={onOpenSignIn}
        onOpenStatus={onOpenStatus ?? (() => onNavSelect?.('system-status'))}
        isMobileMenuOpen={isMobileNavOpen}
        onToggleMobileMenu={() => setIsMobileNavOpen((prev) => !prev)}
      />
      <div className="orq-layout-body">
        <NavigationShell
          activeId={activeNavId}
          onSelect={onNavSelect}
          isMobileOpen={isMobileNavOpen}
          onCloseMobile={() => setIsMobileNavOpen(false)}
          environmentName={environmentName}
        />
        <main className="orq-layout-main" role="main">
          <div className="orq-main-container">
            {children}
          </div>
          <footer className="orq-layout-footer" role="contentinfo">
            <div className="orq-footer-container">
              <div className="orq-footer-left">
                <span className="orq-footer-copy">© 2026 Orqestra Platform. All rights reserved.</span>
                <span className="orq-footer-divider" aria-hidden="true">·</span>
                <span className="orq-footer-status">Enterprise Multi-Tenant</span>
              </div>
              <div className="orq-footer-links">
                <button
                  type="button"
                  className="orq-footer-btn-link"
                  onClick={() => onOpenLegal?.('terms')}
                >
                  Terms of Service
                </button>
                <button
                  type="button"
                  className="orq-footer-btn-link"
                  onClick={() => onOpenLegal?.('privacy')}
                >
                  Privacy Policy
                </button>
                <a href="mailto:support@orqestra.io" className="orq-footer-btn-link">
                  Support
                </a>
              </div>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
};

